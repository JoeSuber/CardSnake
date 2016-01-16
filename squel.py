#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
some db-examination/debug stuff for pasting into ipython console and general convenience
"""
import sys
reload(sys).setdefaultencoding("utf8")
import populate as peep
import pprint
import requests
import json


def cols(sort=True):
    return {'c': sorted(peep.card_db.show_columns('cards')),
            's': sorted(peep.set_db.show_columns('set_infos'))}


def rall(t='cards', db=peep.card_db):
    if t == 'sets':
        t = 'set_infos'
        db = peep.set_db
    return db.cur.execute("SELECT * from {}".format(t)).fetchall()


def look(row_object, *stuff):
    return [row_object[s] for s in stuff]


def mtginfo(site='http://magiccards.info/sitemap.html'):
    ri = requests.get(site).iter_lines()
    mcimap = {}
    for i in ri:
        if '<h3>Expansions</h3>' in i:
            for l in i.split('<a href="'):
                if '/en.html' in l:
                    a, b = l.split('/en.html">')
                    mcimap[a.strip('/').strip()] = b.split('</a> ')[0].strip()
    return mcimap


def jsoninfo():
    mcimap = mtginfo()
    rows = peep.set_db.cur.execute("SELECT code, name, magicCardsInfoCode, card_count from set_infos").fetchall()
    for r in rows:
        #if r['name'] in mcimap.values():
        #    print("removing name: {} ({})".format(r['name'], r['magicCardsInfoCode']))
         #   mcimap.pop(r['magicCardsInfoCode'])
        if r['magicCardsInfoCode'] in mcimap.keys():
            print("mcicode removal: {} ({})".format(r['magicCardsInfoCode'], r['name']))
            mcimap.pop(r['magicCardsInfoCode'])
    with open(peep.__mcisite__, 'wb') as fob:
        json.dump(mcimap, fob)
    return mcimap


def codeinfo():
    mcimap = mtginfo()
    codes = {}
    outcodes = {}
    rows = peep.set_db.cur.execute("SELECT code, name, magicCardsInfoCode, card_count from set_infos").fetchall()
    for r in rows:
        codes[r['code']] = r['magicCardsInfoCode']
    for k, v in mcimap.viewitems():
        if k in codes.values():
            codes.pop(k)
    with open(peep.__notmci__, 'wb') as fob:
        json.dump(codes, fob)
    return codes


def listset(code):
    rows = peep.card_db.cur.execute("SELECT * from cards where code=?", (code,)).fetchall()
    for r in rows:
        print("{}: {} {}".format(r['code'], r['name'], r['pic_link']))


if __name__ == "__main__":
    pprint.pprint(cols())
    pprint.pprint(jsoninfo())
    pprint.pprint(codeinfo())
