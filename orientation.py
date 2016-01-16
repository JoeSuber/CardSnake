#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
lets generate some data to help determine which way is up when looking at a card image
"""
import sys
reload(sys).setdefaultencoding("utf8")
import populate as peep
import os
import json
import gmpy2
from gmpy2 import mpz
import cv2
import numpy as np

#peep.card_db.cur.execute("DROP TABLE orient")

orient_db = peep.DBMagic(DBfn=peep.__sqlcards__,
                         DBcolumns={'orient': peep.createstr.format('orient', peep.__cards_key__)},
                         DB_DEBUG=True)

orient_db.add_columns('orient', {'top_dct': 'TEXT', 'bot_dct': 'TEXT', 'picpath': 'TEXT'})


def dct_hint(im, hsize=32):
    """ because we take the measure against the mean, no need to convert float32.
    returning DCT hash as 64-bit mpz int, which makes popcount exceedingly fast"""
    q = 0
    bumpy = cv2.dct(np.array(cv2.resize(im, dsize=(hsize, hsize),
                                        interpolation=cv2.INTER_AREA), dtype=np.float32))[:8, 1:9]
    for i, j in enumerate((bumpy > np.mean(bumpy)).ravel()):
        if j:
            q += 1 << i
    return mpz(q)


def cards(fs=peep.__mtgpics__):
    cardmap = {}
    for line in peep.card_db.cur.execute("SELECT id, name, code, pic_path from cards").fetchall():
        #print("fs={}   picpath={}".format(fs, line['pic_path']))
        if line['pic_path']:
            cardmap[line['id']] = os.path.join(fs, line['pic_path'])
    return cardmap


def add_dct_data(cardpaths):
    print("starting dct of all {} items".format(len(cardpaths)))
    datas = []
    for k, v in cardpaths.viewitems():
        im = cv2.equalizeHist(cv2.imread(v, cv2.IMREAD_GRAYSCALE))
        height, width = im.shape[:2]
        line = {'id': k, 'pic_path': v, 'top_dct': gmpy2.digits(dct_hint(im[:width*.80, :width])),
                'bot_dct': gmpy2.digits(dct_hint(im[height-width*0.80:height, :width]))}
        datas.append(line)
    print("obtained data, now committing to db")
    orient_db.add_data(datas, 'orient', 'id')
    orient_db.con.commit()

    return datas

def show(cardpaths):
    print("press <esc> to exit the viewer ")
    for k, v in cardpaths.viewitems():
        im = cv2.equalizeHist(cv2.imread(v, cv2.IMREAD_GRAYSCALE))
        height, width = im.shape[:2]
        cv2.imshow('top', im[:width*0.80, :width])
        cv2.imshow('bot', im[height-width*0.80:height, :width])
        ch = cv2.waitKey(0) & 0xff
        if ch == 27:
            cv2.destroyAllWindows()
            break
    return ch

def getdcts(col='top_dct'):
    dcts = orient_db.cur.execute("SELECT top_dct, bot_dct from orient").fetchall()
    ups = [gmpy2.mpz(up['top_dct']) for up in dcts]
    downs = [gmpy2.mpz(down['bot_dct']) for down in dcts]
    upvsup, upvsdown, downvsdown = [], [], []
    for up in ups[12000:13000]:
        upvsup.append(np.mean(np.vstack([gmpy2.hamdist(up, u) for u in ups])))
        upvsdown.append(np.mean(np.vstack([gmpy2.hamdist(up, d) for d in downs])))
    for down in downs[12000:13000]:
        downvsdown.append(np.mean(np.vstack([gmpy2.hamdist(down, d) for d in downs])))


    allup = np.mean(np.vstack(upvsup))
    updown = np.mean(np.vstack(upvsdown))
    dndn = np.mean(np.vstack(downvsdown))

    print(allup, updown, dndn)


def main():
    #ch = show(cards())
    #print ch

    #datas = add_dct_data(cards())
    getdcts()


if __name__ == "__main__":
    exit(main())
