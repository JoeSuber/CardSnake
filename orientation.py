#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
lets generate some data to help determine which way is up when looking at a card image

also, for examination of various generated relations, debugging etc
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
from collections import defaultdict
import pprint

__RAT__ = 0.80  # image height = __RAT__* width. This mostly puts top-image-bottom-border at art-line

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
    """
    sock away top and bottom dcts of pics as persistent 64-bit int
    """
    datas = []
    allin = orient_db.cur.execute("SELECT * from orient").fetchall()
    print("dct-database has {} of {} possible rows. adding remainder".format(len(allin), len(cardpaths)))
    if len(allin) < len(cardpaths):
        for k, v in cardpaths.viewitems():
            if not any([a['picpath'] == os.path.join(v.split(os.path.sep)[-2:]) for a in allin]):
                im = cv2.equalizeHist(cv2.imread(v, cv2.IMREAD_GRAYSCALE))
                height, width = im.shape[:2]
                line = {'id': k, 'pic_path': v, 'top_dct': gmpy2.digits(dct_hint(im[:width*__RAT__, :width])),
                        'bot_dct': gmpy2.digits(dct_hint(im[height-width*__RAT__:height, :width]))}
                datas.append(line)
    print("adding {} new lines of data to a previous {} lines".format(len(datas), len(allin)))
    if datas:
        orient_db.add_data(datas, 'orient', 'id')
        orient_db.con.commit()
    return datas


def show(cardpaths):
    print("press <esc> to exit the viewer ")
    for k, v in cardpaths.viewitems():
        im = cv2.equalizeHist(cv2.imread(v, cv2.IMREAD_GRAYSCALE))
        height, width = im.shape[:2]
        cv2.imshow('top', im[:width*__RAT__, :width])
        cv2.imshow('bot', im[height-width*__RAT__:height, :width])
        ch = cv2.waitKey(0) & 0xff
        if ch == 27:
            cv2.destroyAllWindows()
            break
    return ch


def getdcts():
    dcts = orient_db.cur.execute("SELECT top_dct, bot_dct from orient").fetchall()
    ups = [gmpy2.mpz(up['top_dct']) for up in dcts]
    downs = [gmpy2.mpz(down['bot_dct']) for down in dcts]
    return ups, downs


def npydcts():
    dcts = orient_db.cur.execute("SELECT top_dct, bot_dct, id from orient").fetchall()
    ups = [np.uint64(up['top_dct']) for up in dcts]
    downs = [np.uint64(down['bot_dct']) for down in dcts]
    return ups, downs, [i['id'] for i in dcts]


def idname(id):
    r = peep.card_db.cur.execute("SELECT name, code, id from cards where id=?", (id,)).fetchone()
    return r['name'], r['code'], r['id']


def mean_dct(ups, downs):
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
    return allup, updown, dndn


def find_sames(dcts, ids):
    """
    Parameters
    ----------
    dcts = [dct hash, ...]
    ids = [(name, code), ...] in corresponding order to 'dcts'

    Returns: {dct: [(name, code), (name, code), ...], ...} defaultdict showing "collisions"
    """
    names = defaultdict(list)
    for n, dct in enumerate(dcts):
        if dcts.count(dct) > 1:
            names[dct].append(idname(ids[n]))
    print "quantity of duplicate dct is {}".format(len(names))
    return names


def showpics(ids, wait=0):
    for i in ids:
        r = peep.card_db.cur.execute("SELECT pic_path, code, name from cards where id=?", (i,)).fetchone()
        if r['pic_path']:
            cv2.imshow("{} {} {}".format(r['code'], r['name'], r['pic_path']),
                       cv2.imread(os.path.join(peep.__mtgpics__, r['pic_path'])))
        else:
            print("no pic: {} {}".format(r['name'], r['code']))
    return cv2.waitKey(wait)


def display(sameups, showall=False):
    """
    sameups: list of 3-tuples, [(nametext, cardset, database_id), ...]
    show groups of pics
    """
    for sames in sameups.viewvalues():
        # compare names against first entry, only show when differences
        if showall or any([s[0] != sames[0][0] for s in sames]):
            ch = showpics([s[2] for s in sames])
            if ch == 27:
                cv2.destroyAllWindows()
                break
            else:
                cv2.destroyAllWindows()


def bring_up():
    ch = ''
    cards = peep.card_db.cur.execute("select id, pic_path, name from cards").fetchall()
    while ch != 27:
        results = []
        txt = raw_input("Enter card name:  ")
        if not txt:
            continue
        for c in cards:
            if txt.lower() in c['name'].lower():
                results.append(c['id'])
        if results:
            ch = showpics(results)
        cv2.destroyAllWindows()


def main():
    add_dct_data(cards())
    ups, dns, ids = npydcts()
    uar, dar = np.vstack(np.array(ups, dtype=np.uint64)), np.vstack(np.array(dns, dtype=np.uint64))
    s = len(uar)
    print s, s*2
    big = np.zeros((s, 5), np.uint64)
    big[:s, :1] = uar
    big[:s, 1:2] = dar
    bs = big[:10, :2]
    uniq = np.setxor1d(uar, dar)
    print "uniqelen=", len(uniq)
    #display(find_sames(ups, ids), showall=False)
    bring_up()


if __name__ == "__main__":
    exit(main())
