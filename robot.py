#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
serial interface to g-code driven robot apparatus that takes pictures and moves physical cards around
"""

import serial as ser
import time
import os
import cv2
import numpy as np
from collections import defaultdict, namedtuple, OrderedDict
from operator import itemgetter
from cv2_common import Timer, draw_str
import orientation
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


class Posts(object):
    """
    provides visualization and allows user to warp the a sub-section of the camera image into alignment with
    an 'ideal' image to be used in the card-id process.
    """
    def __init__(self, camx=640, camy=480, yc=445, xc=312):
        self.camx = camx
        self.camy = camy
        self.xc = xc
        self.yc = yc
        # these hard-coded corner values are just starting points, and are adjustable
        self.p1 = (517, 101)
        self.p2 = (541, 368)
        self.p3 = (136, 385)
        self.p4 = (136, 101)
        self.lines = [2, 2, 2, 2]
        self.colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 255)]
        self.radii = [5, 5, 5, 5]
        self.arrows = {81: (-1.0, 0.0), 82: (0.0, -1.0), 83: (1.0, 0.0), 84: (0.0, 1.0)}
        self.arrow_keys = self.arrows.keys()
        self.number_keys = [ord('1'), ord('2'), ord('3'), ord('4')]
        self.current_index = 0
        self.pts1 = np.float32([self.p1, self.p2, self.p3, self.p4])
        self.pts2 = np.float32([[0, 0], [xc, 0],
                                [xc, yc], [0, yc]])
        self.M2 = cv2.getPerspectiveTransform(self.pts1, self.pts2)
        self.ADJUSTING = False

    def draw_guides(self, cam_img):
        if self.ADJUSTING:
            saying = "Use Arrow Keys and Numbers (1-4) to adjust until warp is square"
            for pnt, r, c, ln in zip(self.pts1, self.radii, self.colors, self.lines):
                cv2.circle(cam_img, tuple(pnt), r, c, thickness=ln)
            for line, (label, pnt, hugh) in enumerate(zip(["p1", "p2", "p3", "p4"], self.pts1, self.colors)):
                draw_str(cam_img, (10, 40 + (line * 15)), " =".join([label, str(tuple(pnt))]), hugh)
        else:
            saying = "Press [a] to turn corner-adjustment on/off."
        draw_str(cam_img, (20, 17), saying)
        return cam_img

    def get_warp(self, whole_img):
        return cv2.warpPerspective(whole_img, self.M2, (self.xc, self.yc))

    def check_key(self, ch):
        if ch != 255:
            if ch == ord('a'):
                self.ADJUSTING = not self.ADJUSTING
            if self.ADJUSTING and (ch in self.number_keys):
                self.current_index = self.number_keys.index(ch)
                self.lines, self.radii = [2, 2, 2, 2], [5, 5, 5, 5]
                self.lines[self.current_index] = 4
                self.radii[self.current_index] = 8
            if self.ADJUSTING and (ch in self.arrow_keys):
                self.pts1[self.current_index] += self.arrows[ch]
                self.M2 = cv2.getPerspectiveTransform(self.pts1, self.pts2)


class Robot(object):
    def __init__(self, baud='115200', port='/dev/ttyACM0', readtimer=0, nl='\n', LOAD=True):
        self.baud = baud
        self.port = port
        self.con = ser.Serial(port=port, baudrate=baud, timeout=readtimer)
        self.nl = nl
        self.LOADING = LOAD
        self.do = {'pickup_pos': 'M280 S120 P0' + nl + ' G0 X1',
                   'drop_pos': 'G0 X45',
                   'fan_on': 'M106',
                   'fan_off': 'M107',
                   'servo_drop': 'M280 S57 P0',
                   'servo_up': 'M280 S120 P0',
                   'end_stop_status': 'M119',
                   'positions': 'M114',
                   'stop': 'M410',
                   'raise_hopper': 'G92 Y3' + nl + ' G1 Y0'}
        self.times = {'pickup_pos': 2.7,
                      'drop_pos': 2.6,
                      'fan_on': 0.1,
                      'fan_off': 0.1,
                      'servo_drop': 0.6,
                      'servo_up': 0.5,
                      'end_stop_status': 0.02,
                      'positions': 0.011,
                      'stop': 0.02,
                      'raise_hopper': 0.0}
        self.BLOCKED = False
        time.sleep(0.4)
        self.con.write("M115" + self.nl)    # M115 info string request
        time.sleep(0.5)
        print("serial port: {}   isOpen={}".format(self.con.getPort(), self.con.isOpen()))
        for l in self.con.read(size=self.con.inWaiting()).split(':'):
            print(": {}".format(l))
        # physically home X (arm) Y (hopper) and Z (output bin) to zero positions
        self.con.write("G28 XYZ" + self.nl)
        time.sleep(0.5)
        self.con.write(self.do['drop_pos'] + self.nl + " " + self.do['servo_up'] + self.nl)  # arm out to allow loading
        self.con.write(self.do['fan_off'] + self.nl)
        self.NEED_DROP = False
        self.SHOULD_RETURN = False
        self.ID_DONE = False
        self.PICKING_UP = False
        self.bins = OrderedDict([('Low', 125), ('High', 247.5)])
        self.bin_cuts = OrderedDict([('Low', 0.0), ('High', 0.5)])
        self.bin_sliver = 0.2
        self.con.flush()

    def dothis(self, instruction):
        if instruction in self.do.keys():
            self.con.write(self.do[instruction] + self.nl)
            return self.times[instruction]

        self.con.write(instruction + self.nl)
        return 0.0

    def bin_lookup(self, price, binname='Low'):
        for bk, bv in self.bin_cuts.viewitems():
            if price >= bv:
                binname = bk
        return binname

    def sensor_tripped(self, term='x_max: TRIGGERED', ret_size=109):
        wait = self.dothis('end_stop_status') + time.time()
        while time.time() < wait:
            if self.con.inWaiting() > ret_size:
                return term in self.con.read(size=self.con.inWaiting())
        print("time expired on call to sensor_tripped()")
        return False

    def xyz_pos(self, ret_size=55):
        self.con.flushInput()
        wait = self.dothis("positions") + time.time()
        while time.time() < wait:
            if self.con.inWaiting() > ret_size:
                dd = {}
                for c in self.con.read(size=self.con.inWaiting()).split(' Count')[0].split(' '):
                    d = c.replace('ok', '').replace('\n', '').replace('n', '')
                    if ':' in d:
                        a, b = d.split(':')
                        dd[a.strip()] = b.strip()
                print dd
                return dd
        print("time expired on call to xyz_pos()")
        return {}

    def go_z(self, bin_name, timeconst=0.041):
        newz = float(self.bins[bin_name])
        self.bins[bin_name] -= self.bin_sliver
        curz = float(self.xyz_pos()['Z'])
        x_spot = self.do['drop_pos'].split(' ')[1]
        x_time = self.times['drop_pos']
        z_time = abs(curz - newz) * timeconst
        self.dothis("G1 Z" + str(newz) + " " + x_spot + self.nl)
        return z_time if z_time > x_time else x_time

    def load_hopper(self, move=5.0, top="y_max: TRIGGERED", bottom="y_min: TRIGGERED"):
        """ load cards until bottom switch is triggered, indicating max capacity, but only move
        down while top proximity sensor is triggered. Set self.LOADING false when done"""
        return self.raise_hopper()


def main():
    robot = Robot()
    eyeball = Posts()
    MIN_MATCHES = 15
    DRAW_MATCHES, RUN_FAN, PRINT_GOOD = True, False, True
    MAX_ITEMS = 600
    cardlist = []
    smile = orientation.Simile(just_faces=False)
    pathfront = orientation.peep.__mtgpics__
    looker = cv2.AKAZE_create()
    matcher = cv2.FlannBasedMatcher(orientation.flann_pms, {})
    cam = cv2.VideoCapture(0)
    time.sleep(6)
    wait = time.time()
    bin = "Nada"
    OLD_YMIN = False
    while True:
        __, frame = cam.read()
        showimg = eyeball.draw_guides(frame.copy())
        warp = eyeball.get_warp(frame)
        cv2.imshow("warp", warp)
        cv2.imshow("cam", showimg)
        ch = cv2.waitKey(1) & 0xff
        eyeball.check_key(ch)
        if ch == 27:
            robot.dothis("fan_off")
            cv2.destroyAllWindows()
            break
        if ch == ord('g') and not robot.ID_DONE:
            print ("[g] pressed")
            matcher, cardlist = card_adder(smile.handful(warp), matcher, orientation.orient_db, cardlist,
                                       maxitems=MAX_ITEMS)
            current_kp, matchdict = card_compare(warp, looker, matcher)
            bestmatch = sorted([(indx, matches)
                                for indx, matches in matchdict.viewitems() if len(matches) > MIN_MATCHES],
                               key=lambda x: len(x), reverse=True)
            for indx, matches in bestmatch:
                one_card = cardlist[indx]
                pricestr = 'None'
                pricetag = 0
                priceline = pricer.single_price(one_card.id)[0]
                if priceline:
                    pricetag = priceline[1]
                    pricestr = ", ".join(map(str, priceline)[1:3])
                robot.ID_DONE = True
                bin = robot.bin_lookup(pricetag)
                cv2.imshow("{} {}".format(one_card.name, one_card.code), cv2.drawMatchesKnn(warp, current_kp,
                                                  cv2.imread(os.path.join(pathfront, one_card.pic_path)),
                                                  one_card.kp, matches,
                                                  outImg=np.zeros((eyeball.yc, eyeball.xc * 2, 3), dtype=np.uint8),
                                                  flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS))
                if PRINT_GOOD: print("good match: {} {} (pnts:{})  prices: {}"
                                     .format(one_card.name, one_card.code, len(matches), pricestr))
                break
        if ch == ord('f'):
            RUN_FAN = not RUN_FAN
            if RUN_FAN:
                wait = robot.dothis('fan_on') + time.time()
            else:
                wait = robot.dothis('fan_off') + time.time()
        if robot.ID_DONE and (not robot.PICKING_UP) and (time.time() > wait):
            wait = robot.dothis("pickup_pos") + time.time()
            robot.PICKING_UP = True
        if robot.PICKING_UP and (not robot.NEED_DROP) and (time.time() > wait) and robot.sensor_tripped():
            wait = robot.go_z(bin) + time.time()
            robot.PICKING_UP = False
            robot.ID_DONE = False
            robot.NEED_DROP = True
        if robot.NEED_DROP and (time.time() > wait):
            wait = robot.dothis("servo_drop") + time.time()
            robot.NEED_DROP = False
        YMIN = robot.sensor_tripped(term='y_min: TRIGGERED')
        if OLD_YMIN != YMIN:
            OLD_YMIN = YMIN
            if YMIN:
                robot.dothis("raise_hopper")


if __name__ == "__main__":
    exit(main())