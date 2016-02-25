#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
2) test flann matcher capability to handle multiple sets of objects. Find the trade-offs that are acceptable between
    the quantity of keypoints-per-object (ie probably between 30 - 600) and speed/capacity/accuracy of matcher.
    Allow for testing different flann-parameters or even getting the auto-tune thing working.
    a) key-points could be winnowed by strength or re-computed to a given max/min quantity per pic.

3) in service to both above items, fix-up a bounding box, and a 'shutter-open-close' widget for the camera.
    include rotations / flips to help in determining the orientation / affine transform (if needed) to find proper
    sample from the image. Homography from key-points could be found and coded in to capture to allow convenient
    physical camera offset.
    Find out what the standard deviations, means and medians are for hamming distances when the subject is oriented
    'right-side-up' vs 'upside-down' Build some efficient logic for orientation::Simile that tells this vital bit of
    info given dct_hints..
        a) Build some multiple-sample based recognition into database for the card back (based on input images).
            Perhaps some 'hard-coded' dct_hint could be included in source-code for card backs
"""
import cv2
import numpy as np
import orientation, seemore
from collections import namedtuple, defaultdict
import os


Card = namedtuple('Card', 'name, code, id, pic_path, kp')


def card_corners(camx, camy, xc, yc):
    return (camx - xc)/2, (camy - yc)/2, camx/2 + xc/2, camy/2 + yc/2


def card_compare(imgsamp, look, matchmaker, distance_ratio=0.82):
    """
    Parameters
    ----------
    imgsamp: unprocessed image to be compared against database items
    look: the cv2 detection object (AKAZE, SIFT, ORB, etc)
    matchmaker: the cv2 Flann matcher object
    distance_ratio: used to filter out bad matches

    Returns
    -------
    results: defaultdict(list) has keys that are integer indexes to the list of Card objects.
            Values are lists of cv2.DMatch objects filtered into the appropriate indexes
    """
    results = defaultdict(list)
    kp, desc = look.detectAndCompute(imgsamp, None)
    if desc is None:
        #print ("no descriptors")
        return [], {}
    try:
        for m0, m1 in matchmaker.knnMatch(desc, k=2):
            if m0.distance < (m1.distance * distance_ratio):
                results[m0.imgIdx].append([m0])
    except ValueError:
        print("missing a matchmaker pair")
    return kp, results


def card_adder(prospect_ids, matchmaker, db, currentcards, maxitems=5000):
    """
    Parameters
    ----------
    prospect_ids: list of card ids that may need adding to the actively searched bunch
    matchmaker: cv2.Flann object
    db: card database object
    currentcards: list of Card objects in same order as added to matchmaker
    maxitems: automatic cutoff to limit size of matcher object (for performance reasons)

    Returns
    -------
    matchmaker: the (bigger, maybe) matcher object
    currentcards: now complete list of Card objects
    """
    current_adds = set(prospect_ids) - set([c.id for c in currentcards])

    if ((len(current_adds) + len(currentcards)) > maxitems) and len(currentcards):
        print("exceeded maximum allowed items in matcher object: maxitems = {}".format(maxitems))
        matchmaker.clear()
        currentcards = []

    for sid in current_adds:
        line = db.cur.execute("SELECT name, code, pic_path FROM cards WHERE id=(?)", (sid,)).fetchone()
        kp, desc = orientation.get_kpdesc(sid, columns='ak_points,ak_desc')
        if desc is None:
            print("database has no kp, descriptor entry for {}".format(orientation.idname(sid)))
            continue
        card = Card(line['name'], line['code'], sid, line['pic_path'], kp)
        currentcards.append(card)
        matchmaker.add([desc])
    return matchmaker, currentcards


ui = dict(g="[g]ive the new pics a base-name. Currently: '{}' ",
          p="[p]rint verbose news about the matcher: {}{}bonus info! matcher has {} objects.",
          t="[t]ake a picture: {} with {} errors",
          k="[k]ompare the area in the green box with database items",
          r="[r]un comparisons without pause on every frame: {}",
          e="[e]rasing {} items from cardlist and matcher",
          c="[c]leaning the windows",
          d="[d]rawing Matches set to: {}",
          esc="[esc]ape (exit) the program loop",
          h="[h]elp - show these options")


def main():
    camx, camy = 640, 480   # typical web-cam dimensions
    yc, xc = (445, 312)     # typical pixels for a card
    cdx1, cdy1, cdx2, cdy2 = card_corners(camx, camy, yc, xc)
    MIN_MATCHES = 5
    DRAW_MATCHES, RUN_FREE, PRINT_GOOD = True, True, False
    MAX_ITEMS = 100
    cardlist = []
    user_given_name = None
    M2 = cv2.getRotationMatrix2D((xc/2, xc/2), -90, 1)
    smile = orientation.Simile(just_faces=False)
    pathfront = orientation.peep.__mtgpics__
    looker = cv2.AKAZE_create()
    matcher = cv2.FlannBasedMatcher(orientation.flann_pms, {})
    cam = cv2.VideoCapture(0)
    for vals in ui.viewvalues():
        print(vals)
    while True:
        __, frame = cam.read()
        showimg = frame.copy()
        cv2.rectangle(showimg, (cdx1, cdy1), (cdx2, cdy2), (0, 255, 0))
        cv2.imshow("cam", showimg)
        ch = cv2.waitKey(1) & 0xff
        if ch == ord('r'):
            RUN_FREE = not RUN_FREE
            print(ui['r'].format(RUN_FREE))
        if ch == ord('g'):
            print(ui['g'].format(user_given_name))
            user_given_name = str(raw_input("type in the new pic base-name >>> ")).strip()
        if ch == ord('p'):
            PRINT_GOOD = not PRINT_GOOD
            print(ui['p'].format(PRINT_GOOD, os.linesep, len(cardlist)))
        if ch == ord('t'):
            samp_img = cv2.warpAffine(frame[cdy1:cdy2, cdx1:cdx2], M2, (xc, yc))
            quant, errors = seemore.pic_adder(samp_img, img_name=user_given_name)
            print(ui['t'].format(quant+1, errors))
        if RUN_FREE or (ch == ord('k')):
            samp_img = cv2.warpAffine(frame[cdy1:cdy2, cdx1:cdx2], M2, (xc, yc))
            matcher, cardlist = card_adder(smile.handful(samp_img), matcher, orientation.orient_db, cardlist,
                                           maxitems=MAX_ITEMS)
            cv2.imshow("sample", samp_img)
            current_kp, matchdict = card_compare(samp_img, looker, matcher)
            for indx, matches in matchdict.viewitems():
                if len(matches) > MIN_MATCHES:
                    one_card = cardlist[indx]
                    if not DRAW_MATCHES:
                        cv2.imshow("{} {}".format(one_card.name, one_card.code),
                               cv2.imread(os.path.join(pathfront, one_card.pic_path)))
                        if PRINT_GOOD: print("good match: {} {} #{}"
                                             .format(cardlist[indx].name, cardlist[indx].code, len(matches)))
                    else:
                        cv2.imshow("{} {}".format(one_card.name, one_card.code),
                                   cv2.drawMatchesKnn(samp_img, current_kp,
                                                      cv2.imread(os.path.join(pathfront, one_card.pic_path)),
                                                      one_card.kp, matches, outImg=np.zeros((yc, xc*2, 3),
                                                                                            dtype=np.uint8),
                                                      flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS))
                        if PRINT_GOOD: print("good match: {} {} #{}"
                                             .format(cardlist[indx].name, cardlist[indx].code, len(matches)))
        if ch == ord('e'):
            print(ui['e'].format(len(cardlist)))
            matcher.clear()
            cardlist = []
            ch = ord('c')
        if ch == ord('c'):
            print(ui['c'])
            cv2.destroyAllWindows()
        if ch == ord('d'):
            DRAW_MATCHES = not DRAW_MATCHES
            print(ui['d'].format(DRAW_MATCHES))
        if ch == ord('h'):
            for vals in ui.viewvalues():
                print(vals)
        if ch == 27:
            print(ui['esc'])
            cv2.destroyAllWindows()
            break

if __name__ == "__main__":
    exit(main())
