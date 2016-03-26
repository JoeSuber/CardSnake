#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""

"""
import cv2
import numpy as np
import orientation, seemore
from collections import namedtuple, defaultdict
import os
import pricer

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
    currentcards: now complete list of Card objects in the same order as matchmaker indexes the descriptors
    """
    current_adds = set(prospect_ids) - set([c.id for c in currentcards])

    if ((len(current_adds) + len(currentcards)) > maxitems) and len(currentcards):
        print("exceeded maximum allowed items in matcher object: maxitems = {}".format(maxitems))
        matchmaker.clear()
        currentcards = []

    for sid in current_adds:
        line = db.cur.execute("SELECT name, code, pic_path FROM cards WHERE id=(?)", (sid,)).fetchone()
        kp, desc = orientation.get_kpdesc(sid, c1='ak_points', c2='ak_desc')
        if desc is None:
            print("database has no kp, descriptor entry for {}".format(orientation.idname(sid)))
            continue
        card = Card(line['name'], line['code'], sid, line['pic_path'], kp)
        currentcards.append(card)
        matchmaker.add([desc])
    return matchmaker, currentcards


def undertaker(db=orientation.orient_db, path_front=orientation.peep.__mtgpics__, img_code='USER'):
    """
    remove from database the items (of a particular set-code) that don't have an actual picture
    on their given path. Allows user to simply delete unwanted add-on pics from where they are
    in the local file-system.
    """
    bad_user_stuff = [line['id'] for line in
                     db.cur.execute("SELECT id, pic_path FROM cards WHERE code=?", (img_code,)).fetchall()
                     if not os.path.isfile(os.path.join(path_front, line['pic_path']))]
    print("user stuff without pictures: {}".format(len(bad_user_stuff)))
    for tbl in db.tables:
        db.cur.executemany("DELETE FROM {} WHERE id=?".format(tbl), ((b,) for b in bad_user_stuff))
    db.con.commit()
    return 1


def main():
    camx, camy = 640, 480   # typical web-cam dimensions
    yc, xc = (445, 312)     # typical pixels for a card
    cdx1, cdy1, cdx2, cdy2 = card_corners(camx, camy, yc, xc)
    MIN_MATCHES = 5
    DRAW_MATCHES, RUN_FREE, PRINT_GOOD = True, False, True
    MAX_ITEMS = 500
    cardlist = []
    user_given_name = None
    M2 = cv2.getRotationMatrix2D((xc/2, xc/2), -90, 1)
    smile = orientation.Simile(just_faces=False)
    pathfront = orientation.peep.__mtgpics__
    looker = cv2.AKAZE_create()
    matcher = cv2.FlannBasedMatcher(orientation.flann_pms, {})
    cam = cv2.VideoCapture(0)
    undertaker(img_code='USER')
    ui = dict(g="[g]ive the new pics a base-name. Currently: '{}' ",
                p="[p]rint verbose news about the matcher: {}{}bonus info! matcher has {} objects.",
                t="[t]ake a picture: {} with {} errors",
                k="[k]ompare the area in the green box with database items",
                r="[r]un comparisons continuously, ie. on every frame: {}",
                e="[e]rasing {} items from cardlist and matcher",
                c="[c]lean up the windows",
                d="[d]rawing Matches set to: {}",
                esc="[esc]ape (exit) the program loop",
                h="[h]elp - show these options")
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
                        if PRINT_GOOD: print("good match: {} {} #{}  price: {}"
                                             .format(cardlist[indx].name, cardlist[indx].code, len(matches),
                                                     pricer.single_price(cardlist[indx].id)[0]))
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
            print("")
            for vals in ui.viewvalues():
                print(vals)
        if ch == 27:
            print(ui['esc'])
            cv2.destroyAllWindows()
            break

if __name__ == "__main__":
    exit(main())
