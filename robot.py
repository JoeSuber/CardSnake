#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
serial interface to g-code driven robot apparatus that takes pictures and moves physical cards around
"""

import serial as ser
import time
import cv2
import numpy as np
from collections import deque, defaultdict, namedtuple, OrderedDict
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
    provides visualization and allows user to warp the camera image into perfect alignment with
    an 'ideal' image to be used in the card-id process.
    """
    def __init__(self, camx=640, camy=480, yc=445, xc=312):
        self.camx = camx
        self.camy = camy
        self.xc = xc
        self.yc = yc
        # these hard-coded corner values are just starting points, and are adjustable
        self.p1 = (517, 95)
        self.p2 = (541, 368)
        self.p3 = (134, 385)
        self.p4 = (134, 95)
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
            for line, (label, pnt) in enumerate(zip(["p1", "p2", "p3", "p4"], self.pts1)):
                draw_str(cam_img, (10, 40 + (line * 15)), " =".join([label, str(tuple(pnt))]))
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
                   'drop_pos': 'G1 X45',
                   'fan_on': 'M106',
                   'fan_off': 'M107',
                   'servo_drop': 'M280 S57 P0',
                   'servo_up': 'M280 S120 P0',
                   'end_stop_status': 'M119',
                   'positions': 'M114',
                   'stop': 'M410'}
        self.times = {'pickup_pos': 'M280 S120 P0' + nl + ' G0 X1',
                      'drop_pos': 'G1 X45',
                      'fan_on': 'M106',
                      'fan_off': 'M107',
                      'servo_drop': 'M280 S57 P0',
                      'servo_up': 'M280 S120 P0',
                      'end_stop_status': 'M119',
                      'positions': 'M114',
                      'stop': 'M410'}
        self.BLOCKED = False
        time.sleep(0.7)
        self.con.write("M115" + self.nl)    # M115 info string request
        time.sleep(0.7)
        print("serial port: {}   isOpen={}".format(self.con.getPort(), self.con.isOpen()))
        for l in self.con.read(size=self.con.inWaiting()).split(':'):
            print(": {}".format(l))
        self.con.write("G28 XZ" + self.nl)    # physically home X (arm) and Z (output bin) to zero positions
        time.sleep(.5)
        self.con.write(self.do['drop_pos'] + self.nl + " " + self.do['servo_up'] + self.nl)  # arm out to allow loading
        if self.LOADING:
            print("LOADING: must trigger Y-min to exit loading-mode")

    def dothis(self, instruction):
        if instruction in self.do.keys():
            trans = self.do[instruction]
        else:
            trans = instruction
        if self.con.isOpen():
            self.con.write(trans + self.nl)

    def card_carried(self, term='x_max: TRIGGERED'):
        return term in self.dothis('end_stop_status').split(self.nl)

    def xyz_pos(self):
        self.dothis("positions")
        try:
            return dict([tuple(c.split(':')) for c in self.con.read(size=self.con.inWaiting())
                        .split(' Count')[0].split(' ')])
        except AttributeError:
            time.sleep(.1)
            return dict([tuple(c.split(':')) for c in self.con.read(size=self.con.inWaiting())
                        .split(' Count')[0].split(' ')])

    def raise_hopper(self, nudge=1.55):
        sensor_triggered = self.card_carried(term="y_max: TRIGGERED")

    def load_hopper(self, move=5.0, top="y_max: TRIGGERED", bottom="y_min: TRIGGERED"):
        """ load cards until bottom switch is triggered, indicating max capacity, but only move
        down while top proximity sensor is triggered. Set self.LOADING false when done"""

        return self.raise_hopper()

    def testbot(self, destination):
        self.dothis("G0 Z"+str(int(destination))+self.nl)
        size, c = 0, 0
        while not size:
            size = self.con.inWaiting()
            c += 1
            if size:
                line = self.con.read(size=self.con.inWaiting())
                print(line, " ", c)


def App():
    """ loop and do events based on time.time() and returns from functions """
    ON_HOLD = False
    until = time.time()
    steps = {"id_card": 0.1, "pickup_and_bin_move": 0, "raise": 0, "check_on_board": 0,
             "drop_move": 0, "check_drop": 0, "open_air": 0}
    steploop = deque(steps.keys())
    step = steploop.pop()

    while steploop:
        if (now < until) and not ON_HOLD:
            ON_HOLD = True
            now = time.time()
            until = now + steps[step]


def main():
    robot = Robot()
    eyeball = Posts()
    MIN_MATCHES = 5
    DRAW_MATCHES, RUN_FREE, PRINT_GOOD = True, False, True
    MAX_ITEMS = 500
    cardlist = []
    user_given_name = None
    smile = orientation.Simile(just_faces=False)
    pathfront = orientation.peep.__mtgpics__
    looker = cv2.AKAZE_create()
    matcher = cv2.FlannBasedMatcher(orientation.flann_pms, {})
    cam = cv2.VideoCapture(0)
    time.sleep(9)
    while True:
        __, frame = cam.read()
        showimg = eyeball.draw_guides(frame.copy())
        warp = eyeball.get_warp(frame)
        cv2.imshow("warp", warp)
        cv2.imshow("cam", showimg)
        ch = cv2.waitKey(1) & 0xff
        eyeball.check_key(ch)
        if ch == 27:
            cv2.destroyAllWindows()
            break




if __name__ == "__main__":
    exit(main())