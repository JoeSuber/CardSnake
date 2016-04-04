#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
1) given pic (probably via camera), save it to a local dir, get dct and keypoint/desc info into db
    a) must create 'id' hash, and a meaningful filename, ensuring no collisions on 'id'.
    c) maybe allow user intervention via text entry or gui image selection
    d) todo: for repeated similar user-images, test to see if hamming distances to pre-computed items are always
        significantly lower than against the stock images
    e) build this with inclusion into the robot control loop in mind
"""

import cv2
import orientation
import os
import time
from hashlib import sha1


def pic_adder(img, db=orientation.orient_db, img_dir=None, img_name=None, img_code='USER', img_format='.jpg',
              img_id=None, brothers=[]):
    """
    Allows for adding pics to card db even when they are completely without context... but
    keep as much context as is provided.
    Also, avoid file-name and hash collisions by assigning extra sequential numbers when required.
    'brothers' is by default a list of id's that would have collided if names weren't changed
    The new item still has to be processed by the startup routines to be incorporated into searches
    """
    if img_dir is None:
        img_dir = os.path.join(orientation.peep.__mtgpics__, img_code.upper())
    if not os.path.isdir(img_dir):
        os.mkdir(img_dir)
    if img_name is None:
        img_name = "-".join(time.ctime().replace(':', '>').split(' '))
    if img_id is None:
        img_id = sha1(img_code + img_name).hexdigest()

    check = db.cur.execute("SELECT id, name, number from cards WHERE id=?", (img_id,)).fetchone()
    if check is not None:
        db_name = check['name'].split('|-(')[0]
        if check['name'].count('|-('):
            num = int(check['name'].split('|-(')[-1:][0].strip(')') or '0') + 1
        else:
            num = 0
        new_name = db_name + "|-({})".format(num)
        brothers.append(img_id)
        img_id = sha1(img_code + new_name).hexdigest()
        renew = dict(db=db, img_dir=img_dir, img_name=new_name, img_code=img_code, img_format=img_format,
                     img_id=img_id, brothers=brothers)
        return pic_adder(img, **renew)

    fullpath = os.path.join(img_dir, (img_code.lower() + img_name + img_format))
    unique_path = os.sep.join(fullpath.split(os.sep)[-2:])
    cv2.imwrite(fullpath, img)

    line = dict(id=img_id, code=img_code, name=img_name, pic_path=unique_path, variations=brothers)
    print("saved pic as: {}".format(fullpath))
    return db.add_data([line], 'cards', key_column='id')


if __name__ == "__main__":
    print("")
    print("This helps the user create pictures and data beyond the stock stuff.")
    print("It has functions used by the other programs. Run educator.py")
    print("with something of interest as your camera's target. ")
    print("Then exit & run 'popu_pic_orient.py' to digest the new pictures")
    print("into the database. Now your machine can recognize them if they have some texture. ;}")
    exit()
