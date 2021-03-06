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


def card_compare(imgsamp, look, matchmaker, distance_ratio=0.84):
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
    provides visualization and allows user to warp a sub-section of the camera image into alignment with
    an 'ideal' image to be used in the card-id process.
    """
    def __init__(self, camx=640, camy=480, yc=445, xc=312):
        self.camx = camx
        self.camy = camy
        self.xc = xc
        self.yc = yc
        # these hard-coded corner values are just starting points, and are adjustable
        self.p1 = (536, 79)
        self.p2 = (554, 365)
        self.p3 = (137, 377)
        self.p4 = (134, 85)
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
            for line, (label, pnt, hue) in enumerate(zip(["p1", "p2", "p3", "p4"], self.pts1, self.colors)):
                draw_str(cam_img, (10, 40 + (line * 15)), " =".join([label, str(tuple(pnt))]), color=hue)
        else:
            saying = "Press [a] to turn corner-adjustment on/off."
        draw_str(cam_img, (20, 17), saying)
        return cam_img

    def show_card_info(self, texts, chalkboard, max_expansion=2.6, topleft=(5, 5)):
        """ take a list of text lines and draw each so it fits in most of the width of the given image"""
        startx, starty = topleft
        max_x = chalkboard.shape[1] - startx * 2    # leaves margins
        for txt in texts:
            (sx, sy), baseline = cv2.getTextSize(txt, fontFace=cv2.FONT_HERSHEY_PLAIN, fontScale=1, thickness=2)
            # baseline: straggling font-pixels extending below base of most letters, i.e. g p q
            sy += baseline * 0.5
            size_ratio = min(max_x / sx, max_expansion)
            starty += (int(sy * size_ratio) + 2)
            draw_str(chalkboard, (startx, starty), txt, font=cv2.FONT_HERSHEY_PLAIN, size=size_ratio, color=(0, 255, 0))
        return chalkboard

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
    """
    for initializing and running the interface between cpu and robot firmware via serial link
    """
    def __init__(self, baud='115200', port='/dev/ttyACM0', readtimer=0, nl='\n', LOAD=True):
        self.baud = baud
        self.port = port
        self.con = ser.Serial(port=port, baudrate=baud, timeout=readtimer)
        self.nl = nl
        self.LOADING = LOAD
        self.do = {'pickup_pos': 'G0 X1',
                   'drop_pos': 'G0 X52',
                   'fan_on': 'M106',
                   'fan_off': 'M107',
                   'servo_drop': 'M280 S57 P0',
                   'servo_up': 'M280 S120 P0',
                   'end_stop_status': 'M119',
                   'positions': 'M114',
                   'stop': 'M410'}
        self.times = {'pickup_pos': 3,
                      'drop_pos': 3,
                      'fan_on': 0.1,
                      'fan_off': 0.1,
                      'servo_drop': 0.6,
                      'servo_up': 2.0,
                      'end_stop_status': 0.1,
                      'positions': 0.06,
                      'stop': 0.02}
        self.sensor_keys = ["x_min", "y_min", "z_min", "x_max", "y_max"]
        for w in xrange(5):
            print("waiting {} seconds to init serial".format(5 - w))
            time.sleep(1)
        print("serial portisOpen={}".format(self.con.isOpen()))
        # physically home X (arm) Y (hopper) and Z (output bin) to zero positions
        self.con.write("G28 XZ" + nl)
        self.con.write("G28 Y" + nl)
        time.sleep(0.5)

        # arm 'X' swing out to allow loading of hopper
        self.con.write(self.do['drop_pos'] + nl + " " + self.do['servo_up'] + nl)
        self.con.write(self.do['fan_off'] + nl)
        self.NEED_DROP = False
        self.CARD_CARRIED = False
        self.ID_DONE = False
        self.PICKING_UP = False

        # adjust sort categories quantity and bin position here:
        self.bins = OrderedDict([('Low', 125), ('High', 247.5), ('NoID', 50.0)])
        self.bin_cuts = OrderedDict([('Low', 0.0), ('High', 0.5), ('NoID', 10000.0)])
        self.bin_sliver = 0.2
        self.LOADING = True
        #tl = self.con.readline()
        #while tl:
        #    print("startup: {}".format(tl.strip()))
        #    tl = self.con.readline()
        r = self.con.read(self.con.inWaiting())
        for p in r.split('echo:'):
            print p

    def dothis(self, instruction):
        """ sends instruction to robot and returns the estimated execution time if available """
        if instruction in self.do.keys():
            self.con.write(self.do[instruction] + self.nl)
            return self.times[instruction]
        self.con.write(instruction + self.nl)
        return 0.0

    def bin_lookup(self, price, binname=None):
        """returns the bin-name the card-price should be sorted into"""
        for bk, bv in self.bin_cuts.viewitems():
            if price >= bv:
                binname = bk
        return binname

    def sensor_stats(self, min_ret=99, retry=0):
        """returns dict of end-stop sensors, keyed by sensor name, with values of 'open' or 'TRIGGERED'"""
        extra_time = 0
        if retry > 5:
            extra_time = 0.1 * retry
            print("extra time: {} sec".format(extra_time))
        if retry > 32:
            print("too many retries of sensors = {}".format(retry))
            return {'y_max': "TRIGGERED", 'x_max': 'y_is_fake!'}

        wait = self.dothis('end_stop_status') + time.time() + extra_time
        while (time.time() < wait) and (self.con.inWaiting() < min_ret):
            pass
        sensordict = dict([tuple(chunk.split(": ")) for chunk in self.con.read(size=self.con.inWaiting()).split(self.nl)
                    if (': ' in chunk) and (('_min' in chunk) or ('_max' in chunk))])
        skeys = sensordict.keys()
        if all([sk in skeys for sk in self.sensor_keys]):
            return sensordict
        retry += 1
        # print("Retry sensor_stats() #{}".format(retry))
        return self.sensor_stats(min_ret=min_ret, retry=retry)

    def xyz_pos(self, min_ret=59):
        """ returns dict of current stepper DESTINATIONS (in float(mm)) keyed by single-letter axis names"""
        wait = self.dothis("positions") + time.time()
        # start = time.time()
        must_have = ['X', 'Y', 'Z', 'E']
        xyz_dict = {}
        while time.time() < wait and (self.con.inWaiting() < min_ret):
            pass
        # finalwait = self.con.inWaiting()
        for positions in [ps.split(' Count ')[0] for ps in self.con.read(size=self.con.inWaiting()).split(self.nl)
                          if ' Count ' in ps]:
            if all([axis in positions for axis in must_have]):
                for p in positions.split(" "):
                    if ":" in p:
                        k, v = p.split(":")
                        xyz_dict[k.strip()] = float(v.strip())
        # print("actual speed: {}, ret: {}".format(time.time() - start, finalwait))
        return xyz_dict or self.xyz_pos(min_ret=min_ret-1)

    def go_xz(self, bin_name, timeconst=0.07, reverse=False):
        """ given a destination bin, position everything for the drop, while decrementing for the next drop into the bin and
        return the estimated time from the present when the drop can happen """
        back = 1 if not reverse else -1
        newz = float(self.bins[bin_name])
        self.bins[bin_name] -= (self.bin_sliver * back)
        curz = self.xyz_pos()['Z']
        if not reverse:
            x_spot = self.do['drop_pos'].split(' ')[1]
            x_time = self.times['drop_pos']
        else:
            x_time, x_spot = 0, ""
        z_time = abs(curz - newz) * timeconst
        self.dothis("G1 Z" + str(newz) + " " + x_spot)
        return z_time if z_time > x_time else x_time

    def hopper_up(self, y_current=None, bite=1.1, timeconst=0.7):
        """ raise the input hopper by a little bit, return the seconds it is estimated to take"""
        if y_current is None:
            try:
                y_current = self.xyz_pos()['Y']
            except KeyError:
                print("WARNING: hopper_up couldn't get 'Y' starting position. Moving to zero + 1.")
                y_current = 0
        self.dothis("G0 Y{}".format(y_current + bite))
        return bite * timeconst

    def load_hopper(self, move=10.0, y_top=220):
        """ load cards until bottom switch is triggered, indicating max capacity, but only move
        down while top proximity sensor is triggered. Set self.LOADING false when done"""
        # first move up until proximity sensor is triggered to get the platform up top
        print(" - Initializing hopper upwards (until top sensor triggered) - ")
        self.dothis("G0 Y{}".format(y_top))
        power_warn_time = time.time() + 22.0
        INITIALIZE_UP = True
        while INITIALIZE_UP:
            sensor = self.sensor_stats()
            if time.time() > power_warn_time:
                power_warn_time = time.time() + 2.0
                print("Is the power-supply on? If not, break and start over.")
                print("sensors say: {}".format(sensor))
            if 'TRIG' in sensor['y_max']:
                print("top sensor = {}".format(sensor['y_max']))
                time.sleep(self.dothis("stop"))
                INITIALIZE_UP = False
        xyz = self.xyz_pos()
        print("LOAD THE HOPPER. Loading ends when bottom limit switch is triggered.")
        print("Positions:  {}".format(", ".join([k + ":" + str(v) for k, v in xyz.viewitems()])))
        new_sweep = True
        destination = max((xyz['Y'] - move), 0)
        start = time.time()
        while self.LOADING:
            sensor = self.sensor_stats()
            if 'TRIG' in sensor['y_min']:
                self.dothis("stop")
                self.dothis("G92 Y0")
                self.dothis("G0 Y0")
                self.LOADING = False
                continue
            if 'TRIG' in sensor['y_max'] and new_sweep:
                print("moving down to: Y={}".format(destination))
                self.dothis("G0 Y{}".format(destination))
                start = time.time()
                new_sweep = False
            if 'open' in sensor['y_max'] and not new_sweep:
                print("top sensor Open after {} seconds...".format(time.time()-start))
                new_sweep = True
                xyz = self.xyz_pos()
                if 'Y' in xyz.keys():
                    destination = max((xyz['Y'] - move), 0)
                else:
                    print("BAD XYZ: {}".format(", ".join([k + ":" + str(v) for k, v in xyz.viewitems()])))
        xyz = self.xyz_pos()
        print("DONE LOADING")
        print("Positions:  {}".format(", ".join([k + ":" + str(v) for k, v in xyz.viewitems()])))
        nudge_up = True
        wait = 0
        sensor = self.sensor_stats()
        while nudge_up:
            if time.time() > wait:
                wait = self.hopper_up() + time.time()
                sensor = self.sensor_stats()
            if "TRIG" in sensor['y_max']:
                nudge_up = False
        time.sleep(self.dothis('fan_on'))
        return self.hopper_up(bite=0.2)


def main():
    robot = Robot()
    eyeball = Posts()
    DEBUG = True
    nudge_count = 0
    MIN_MATCHES = 13
    MAX_ITEMS = 8
    MAX_FAILS = 40
    RUN_FAN = False
    GRIP, TRIP = 1, 1
    ROBOGO = False
    BIN_REVERSE = False
    cardlist = []
    smile = orientation.Simile(just_faces=False)
    pathfront = orientation.peep.__mtgpics__
    looker = cv2.AKAZE_create()
    matcher = cv2.FlannBasedMatcher(orientation.flann_pms, {})
    cam = cv2.VideoCapture(0)
    time.sleep(6)
    wait = time.time()
    print(" -- Loading Hopper --")
    robot.load_hopper()
    bin_name = robot.bin_lookup(0.0)
    old_window = ""
    id_failure_cnt = 0
    while True:
        __, frame = cam.read()
        showimg = eyeball.draw_guides(frame.copy())
        warp = eyeball.get_warp(frame)
        cv2.imshow("warp", warp)
        cv2.imshow("cam", showimg)
        ch = cv2.waitKey(1) & 0xff
        eyeball.check_key(ch)
        if ch == 27:
            robot.dothis("stop")
            robot.dothis("fan_off")
            cv2.destroyAllWindows()
            break
        if ch == ord('q'):
            print robot.sensor_stats(min_ret=100)
        if ch == ord('w'):
            print robot.xyz_pos()
        if ch == ord('e'):
            print("i'm [e] pressed!")
            ee = smile.updown(warp)
            print("DIST:   vs UP:    vs DOWN:")
            for q in sorted(ee.keys()):
                print("{:6} - {:6}  - {:6}".format(q, ee[q][0], ee[q][1]))
        if ch == ord('r'):
            print("[r] cards in matcher: {}".format(len(cardlist)))
            for n, card in enumerate(cardlist):
                print("{:3}: {:4} - {}  #kp={}".format(n, card.code, card.name, len(card.kp)))
        if ch == ord('f'):
            RUN_FAN = not RUN_FAN
            if RUN_FAN:
                wait = robot.dothis('fan_on') + time.time()
            else:
                wait = robot.dothis('fan_off') + time.time()
        if ch == ord('g'):
            ROBOGO = not ROBOGO
            print("ROBOGO = {}".format(ROBOGO))

        if ROBOGO and not robot.ID_DONE:
            old_cardlist_len = len(cardlist)
            matcher, cardlist = card_adder(smile.fistfull(warp, trips=TRIP, grip=GRIP), matcher, orientation.orient_db,
                                           cardlist, maxitems=MAX_ITEMS)
            current_kp, matchdict = card_compare(warp, looker, matcher)
            texture = len(current_kp)
            if texture < (MIN_MATCHES * 3):
                print("WARNING, not enough texture in input image (kp={})".format(texture))
            bestmatch = sorted([(i, matches) for i, matches in matchdict.viewitems()
                                if len(matches) > (MIN_MATCHES + texture) / 6],
                               key=lambda x: len(x[1]), reverse=True)
            if not bestmatch:
                id_failure_cnt += 1
                msg = ""
                if (len(cardlist) == old_cardlist_len):
                    GRIP += 1
                    TRIP += np.random.randint(-1, 3)
                    if (TRIP > 4) or (TRIP < 0):
                        TRIP = 1
                    msg = ", and nothing new added to matcher(len={}) GRIP={}, TRIP={}"\
                        .format(old_cardlist_len, GRIP, TRIP)
                if DEBUG: print("No luck: {} fails{}".format(id_failure_cnt, msg))
            if len(bestmatch) > 1:
                GRIP = 1
                if DEBUG: print("Has {} candidates".format(len(bestmatch)))
            if (id_failure_cnt > MAX_FAILS) and not bestmatch:
                # send the card to the unidentified group/bin
                cardlist, GRIP, TRIP = [], 1, 1
                matcher.clear()
                robot.ID_DONE = True
                bin_name = robot.bin_lookup(10000.1)
                print("Couldn't match this in {} tries".format(id_failure_cnt))
                id_failure_cnt = 0
            for indx, matches in bestmatch:
                one_card = cardlist[indx]
                pricestr = 'None'
                pricetag = 0
                priceline = pricer.single_price(one_card.id)[0]
                if priceline:
                    pricetag = priceline[1]
                    pricestr = "$" + " ,$".join(map(str, priceline)[1:3])
                bin_name = robot.bin_lookup(pricetag)
                new_window = "{} {} | {}".format(one_card.name, one_card.code, pricestr)
                warp = eyeball.show_card_info(new_window.split(" | "), warp, max_expansion=2.6, topleft=(5, 5))
                cv2.imshow(new_window, cv2.drawMatchesKnn(warp, current_kp,
                                                cv2.imread(os.path.join(pathfront, one_card.pic_path)),
                                                  one_card.kp, matches,
                                                  outImg=np.zeros((eyeball.yc, eyeball.xc * 2, 3), dtype=np.uint8),
                                                  flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS))
                if old_window:
                    cv2.destroyWindow(old_window)
                old_window = new_window
                id_failure_cnt = 0
                robot.ID_DONE = True
                # only do all this for the first card on the 'bestmatch' list!
                break

        # with card identified, begin moving the robot
        current_time = time.time()

        if robot.ID_DONE and (not robot.PICKING_UP) and (not robot.NEED_DROP) and (current_time > wait):
            if DEBUG: print("moving arm over hopper")
            wait = robot.dothis("pickup_pos") + time.time()
            wait += (robot.dothis("servo_up") * 0.5)
            robot.PICKING_UP = True

        sens = robot.sensor_stats()
        # if DEBUG: print("{}".format(sens))
        if robot.PICKING_UP and (current_time > wait):
            if DEBUG: print("checking that hopper is high enough")
            if "op" in sens['y_max']:
                if DEBUG: print("raising hopper by default amount")
                wait = robot.hopper_up() + time.time()
            if "op" in sens['x_max'] and nudge_count < 12:
                if DEBUG: print("raising hopper by a nudge {}".format(nudge_count))
                robot.hopper_up(0.1)
            if DEBUG: print("sensor indicates card on board")
            robot.CARD_CARRIED = True
            robot.PICKING_UP = False

        if robot.CARD_CARRIED and (current_time > wait):
            if DEBUG: print("card is moving out for bin drop")
            wait = robot.go_xz(bin_name) + time.time()
            robot.CARD_CARRIED = False
            robot.PICKING_UP = False
            robot.NEED_DROP = True

        if robot.NEED_DROP and (current_time > wait):
            if DEBUG: print("checking that card made it to drop zone")
            sens = robot.sensor_stats()
            if "op" in sens['x_max']:
                if DEBUG: print("*** arrived at drop zone empty! *** going back to get card")
                wait = robot.hopper_up(0.1) + time.time() + robot.go_xz(bin_name, reverse=True)
                robot.NEED_DROP = False
            else:
                if DEBUG: print("Dropping card into bin")
                wait = robot.dothis('servo_drop') + time.time()
                robot.NEED_DROP = False
                robot.ID_DONE = False


if __name__ == "__main__":
    exit(main())