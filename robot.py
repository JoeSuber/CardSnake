#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
serial interface to g-code driven robot apparatus that takes pictures and moves physical cards around
"""

import serial as ser
import time


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
                   'positions': 'M114'}
        time.sleep(0.2)
        self.con.write("M115" + self.nl)    # M115 info string request
        time.sleep(0.5)
        print("serial port: {}   isOpen={}".format(self.con.getPort(), self.con.isOpen()))
        for l in self.con.read(size=self.con.inWaiting()).split(':'):
            print(": {}".format(l))
        self.con.write("G28 XZ" + self.nl)    # physically home X (arm) and Z (output bin) to zero positions
        time.sleep(.5)
        self.con.write(self.do['drop_pos'] + self.nl + " " + self.do['servo_up'] + self.nl)  # move arm out to allow loading
        if self.LOADING:
            print("LOADING hopper by default: must trigger Y-min to exit loading-mode")

    def dothis(self, instruction, sleep=0.1):
        if instruction in self.do.keys():
            trans = self.do[instruction]
        else:
            trans = instruction

        if self.con.isOpen():
            self.con.write(trans + self.nl)
            time.sleep(sleep)
        else:
            print("could not send: {}".format(trans))
            print("connection to {} is not open".format(self.con.getPort))
        return self.con.read(size=self.con.inWaiting())

    def card_carried(self, term='x_max: TRIGGERED'):
        return term in self.dothis('end_stop_status').split(self.nl)

    def xyz_pos(self):
        try:
            return dict([tuple(c.split(':')) for c in self.dothis("positions").split(' Count')[0].split(' ')])
        except ValueError:
            return self.xyz_pos()

    def raise_hopper(self, nudge=1.55):
        sensor_triggered = self.card_carried(term="y_max: TRIGGERED")
        target = float(self.xyz_pos()['Y']) - nudge
        if not sensor_triggered and (nudge > 0):
            _ = self.dothis("G0 Y" + str(target))
            return self.raise_hopper(nudge=(nudge - 0.4))
        return self.dothis("G0 Y" + str(target))

    def load_hopper(self, move=5.0, top="y_max: TRIGGERED", bottom="y_min: TRIGGERED"):
        """ load cards until bottom switch is triggered, indicating max capacity, but only move
        down while top proximity sensor is triggered. Set self.LOADING false when done"""
        goal = float(self.xyz_pos()['Y'])
        print("You are in loading mode! (must press hopper limit switch to exit)")
        # first push down to keep sensor uncovered. break when limit switch is triggered
        while self.LOADING:
            endstops = self.dothis('end_stop_status').split(self.nl)
            if bottom in endstops:
                print("Maximum hopper position indicated")
                self.LOADING = False
                break
            current = float(self.xyz_pos()['Y'])
            if top in endstops:
                goal = current + move
            else:
                goal = current
            _ = self.dothis("G0 Y" + str(goal))

        # next push back up to be in "ready-to-run" position
        return self.raise_hopper()


def main():
    robot = Robot()
    retline = robot.dothis("pickup_pos")
    print("ret: {}".format(retline))
    robot.con.close()


if __name__ == "__main__":
    exit(main())