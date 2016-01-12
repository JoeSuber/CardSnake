"""
create local pic-path column in the cards database (if none)
create card count column in sets db
get a map of setcode: max_quantity for each set in sets db that doesn't have it
load from db and check that pics paths are present and valid
get the missing pics of cards downloaded to a local directory structure.
record the paths in the database.
"""

import populate as peep
import requests, grequests
import os
import cv2
import numpy as np

__db_pic_col__ = {'pic_path': 'TEXT'}
__db_link__ = {'pic_link': 'TEXT'}
__db_card_count__ = {'card_count': 'INTEGER'}
__mci_jpg__ = 'http://magiccards.info/scans/en/{}/{}.jpg'
__mci_set_stub__ = "http://magiccards.info/{}/en.html"
__mci_parser__ = '<td><a href="/{}/en/'


def setcodeinfo():
    """
    returns {'official' set code: magicCardsInfo code, 'ISD': 'isd'...}
    """
    return {k: v for k, v in peep.set_db.cur.execute("select code, magicCardsInfoCode from {}"
                                                     .format(peep.__sets_t__, )).fetchall()}


def linkup(line):
    # in: '    <td><a href="/isd/en/2.html">Angel of Flight Alabaster</a></td>'
    # out: ('Angel of Flight Alabaster', http://magiccards.info/scans/en/isd/2.jpg')
    a, b = line.split('.html">')
    ms, num = a.split('    <td><a href="/')[1].split('/en/')
    name = b.split('</a>')[0]
    return name, __mci_jpg__.format(ms, num)


def setlist_links(mci_setcode):
    """
    mci_setcode: string from database ie 'isd'
    return: for all images in set {'Name of Card': 'http://address-to-image.jpg', ...}
    """
    ri = requests.get(__mci_set_stub__.format(mci_setcode)).iter_lines()
    return dict([linkup(i) for i in ri if __mci_parser__.format(mci_setcode) in i])


def card_counts(counter_col):
    current_counts, old_counts, needs_links = {}, {}, {}
    old_counts = dict(peep.set_db.cur.execute("select {},{} from {}"
                                              .format(u'code', counter_col, peep.__sets_t__)).fetchall())

    for kkk, mci in setcodeinfo().viewitems():
        hits = peep.card_db.cur.execute("select code from {} WHERE code=?"
                                        .format(peep.__cards_t__), (kkk,)).fetchall()
        current_counts[kkk] = len(hits)
        if current_counts[kkk] != old_counts[kkk]:
            print("ATTN: cards in set {} changed from {} to {}".format(kkk, old_counts[kkk], current_counts[kkk]))
            peep.set_db.cur.execute("UPDATE {} SET {}=({}) WHERE {}='{}'".format(peep.__sets_t__,
                                                                             counter_col,
                                                                             current_counts[kkk],
                                                                             u'code', kkk))
            needs_links.update({kkk: mci})
    peep.set_db.con.commit()
    return needs_links


def populate_links(setcodes):
    sql = '''SELECT id, name, imageName from {} where code=?'''.format(peep.__cards_t__)
    usql = '''UPDATE {} SET pic_link=? WHERE id=?'''.format(peep.__cards_t__)
    for s, mci in setcodes.viewitems():
        work = peep.card_db.cur.execute(sql, (s,)).fetchall()
        links = setlist_links(mci)
        print len(work), len(links)
        # assert(len(work) == len(links))
        print links
        used = []
        trouble = []
        for t, w in enumerate(work):
            for n, (k, v) in enumerate(links.viewitems()):
                if n in used:
                    continue
                if (w['name'].strip() == k.strip()) or (w['imageName'].strip() == k.strip()):
                    peep.card_db.cur.execute(usql, (v, w['id']))
                    used.append(n)
                    trouble.append(t)
                    continue

        if len(used) != len(work):
            print(" {} : {} *** populate links {} of {} matched ***".format(s, mci, len(used), len(work)))
            for x in xrange(t):
                if x not in trouble:
                    print("{}".format(work[x]['name']))
    peep.card_db.con.commit()


def main():
    peep.card_db.add_columns(peep.__cards_t__, __db_pic_col__)
    peep.card_db.add_columns(peep.__cards_t__, __db_link__)
    peep.set_db.add_columns(peep.__sets_t__, __db_card_count__)
    l = ['id', 'originalType', 'code', 'reserved', 'toughness', 'text', 'supertypes', 'number', 'releaseDate',
         'colors', 'names', 'subtypes', 'flavor', 'border', 'timeshifted', 'colorIdentity', 'layout', 'multiverseid',
         'source', 'imageName', 'types', 'manaCost', 'type', 'legalities', 'life', 'power', 'watermark', 'printings',
         'loyalty', 'hand', 'starter', 'mciNumber', 'originalText', 'name', 'artist', 'variations', 'rulings', 'rarity',
         'cmc', 'pic_path', 'pic_link']

    print peep.card_db.show_columns(peep.__cards_t__)

    # for testing
    peep.set_db.cur.execute("UPDATE set_infos SET card_count=0")
    peep.card_db.con.commit()
    # # # # # # #

    populate_links(card_counts(__db_card_count__.keys()[0]))

        #for k, v in setcodeinfo().viewitems():

        #unsent = [grequests.get(need) for need in checkimages(k, v)]

    it = peep.card_db.cur.execute("SELECT * FROM cards").fetchall()
    for t in it:
        print("{}".format(t['pic_link']))

    return 1

if __name__ == "__main__":
    exit(main())

