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


def linknull(codes, db=None, t='cards'):
    if db is None:
        db = peep.card_db
    for n, c in enumerate(codes):
        db.cur.execute("UPDATE {} SET pic_path=NULL, pic_link=NULL WHERE code=?".format(t), (c,))
    db.con.commit()
    print("{} had pic_path set null".format(codes))


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
    for k, v in codes.items():
        if v in mcimap.values():
            codes.pop(k)
    with open(peep.__notmci__, 'wb') as fob:
        json.dump(codes, fob)
    return codes


def listset(code):
    rows = peep.card_db.cur.execute("SELECT * from cards where code=?", (code,)).fetchall()
    for r in rows:
        print("{}: {} {}".format(r['code'], r['name'], r['pic_link']))


def main():
    pprint.pprint("columns: {}".format(cols()))
    pprint.pprint(jsoninfo())
    pprint.pprint(codeinfo())
    #oddities = ["phenomenon", "plane", "token", "scheme", "vanguard"]
    #linknull(['9ED', '8ED', 'CPK', 'S00', 'DD2', 'CST', 'PC2', 'HOP'])

    for r in rall(t='cards'):
        if r['code'] == '9ED':
            print("       *   *     *   *  ")
            p = ["{}: {}".format(a, r[a]) for a in r.keys() if r[a]]
            for l in p:
                print l
            #print r['layout'], r['name'], r['code'], r['pic_link']
    return 1


if __name__ == "__main__":
    exit(main())
