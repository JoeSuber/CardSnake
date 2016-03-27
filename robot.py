#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
serial interface to g-code driven robot apparatus that takes pictures and moves physical cards around
"""

import serial as ser
import time


class Robot(object):
    def __init__(self, baud='115200', port='/dev/ttyACM0', readtimer=0):
        self.baud = baud
        self.port = port
        self.con = ser.Serial(port=port, baudrate=baud, timeout=readtimer)
        self.do = {'pickup_pos': 'G1 X1',
                   'drop_pos': 'G1 X45',
                   'fan_on': 'M106',
                   'fan_off': 'M107',
                   'servo_drop': 'M280 S57 P0',
                   'servo_up': 'M280 S120 P0',
                   'end_stop_status': 'M119',
                   'positions': 'M114'}
        time.sleep(0.2)
        self.con.write("M115\n")    # M115 info string request
        time.sleep(0.5)
        print("serial port: {}   isOpen={}".format(self.con.getPort(), self.con.isOpen()))
        for l in self.con.read(size=self.con.inWaiting()).split(':'):
            print(": {}".format(l))
        self.con.write("M119\n")    # M119 end stop status
        self.con.write("G28 XZ")

    def dothis(self, instruction, newline='\n'):
        if instruction in self.do.keys():
            trans = self.do[instruction]
        else:
            trans = instruction

        if self.con.isOpen():
            self.con.write(trans + newline)
            time.sleep(0.1)
        else:
            print("could not send: {}".format(trans))
            print("connection to {} is not open".format(self.con.getPort))
        return self.con.read(size=self.con.inWaiting())


def main():
    robot = Robot()
    retline = robot.dothis("pickup_pos")
    print("ret: {}".format(retline))
    robot.con.close()


if __name__ == "__main__":
    exit(main())