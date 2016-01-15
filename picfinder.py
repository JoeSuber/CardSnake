#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
The json data for magic sets is splotchy at best. If card numbers are present, they are used,
but matching by name is often required even though many cards share the same name! Even inside
a set of cards this can be the case (Swamp, Swamp, Swamp).
Sometimes names don't match due to differences in unicode-points or even typos.
Levenshtein distance is the last resort to try and get the match to a picture-link.

create local pic-path column in the cards database (if none)
create card count column in sets db
get a map of setcode: max_quantity for each set in sets db that doesn't have it
load from db and check that pics paths are present and valid
get the missing pics of cards downloaded to a local directory structure.
record the paths in the database.
"""
import sys
reload(sys).setdefaultencoding("utf8")
import populate as peep
import requests, grequests
from collections import deque, defaultdict, Counter
import Levenshtein as leven
from operator import itemgetter

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
    returns {'official' set code: magicCardsInfo code, 'ISD': 'isd', ...}
    """
    return {k: v for k, v in peep.set_db.cur.execute("select code, magicCardsInfoCode from {}"
                                                     .format(peep.__sets_t__, )).fetchall()}


def linkup(line):
    # in: '    <td><a href="/isd/en/2.html">Angel of Flight Alabaster</a></td>'
    # out: ('Angel of Flight Alabaster', http://magiccards.info/scans/en/isd/2.jpg')
    a, b = line.split('.html">')
    ms, num = a.split('    <td><a href="/')[1].split('/en/')
    name = b.split('</a>')[0]
    return __mci_jpg__.format(ms, num), name


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


def num_from_urls(urls, num):
    # must split it out to avoid finding '1' in '100'
    for u in urls:
        #print "urls u:", u
        if num == u.split('/')[6].split('.jpg')[0]:
            return u
    return False


def populate_links(setcodes):
    sql = '''SELECT id, name, imageName, number from {} where code=?'''.format(peep.__cards_t__)
    usql = '''UPDATE {} SET pic_link=? WHERE id=?'''.format(peep.__cards_t__)
    for s, mci in setcodes.viewitems():
        if mci is None:
            print("ATTENTION: {} has no magiccards.info code, and will get no pics from there!".format(s))
            continue
        work = deque(peep.card_db.cur.execute(sql, (s,)).fetchall())
        starting_work = len(work)
        links = setlist_links(mci)
        if len(links) != starting_work:
            if len(links) < starting_work:
                box_set_code = mci[:2] + 'b'
                links.update(setlist_links(box_set_code))
            print(u"{} aka {}: has {} web-based, but {} local items".format(s, mci, len(links), starting_work))

        for x in xrange(len(work)):
            w = work.pop()
            num, result = w['number'], False
            if num:
                result = num_from_urls(links.keys(), w['number'])
            if result:
                peep.card_db.cur.execute(usql, (result, w['id']))
                links.pop(result)
            else:
                work.appendleft(w)

        #print(u"numbermatching: of {} db entries, {} remain{} for set='{}' aka http://magiccards.info/{}/en.html"
        #     .format(starting_work, len(work), u's' if len(work) == 1 else u'', s, mci))

        intermediate_work = len(work)

        revlinks = defaultdict(list)
        for k, v in links.viewitems():
            revlinks[v.encode('utf-8')].append(k)
        for name_col in ['name', 'imageName']:
            for x in xrange(len(work)):
                w = work.pop()
                try:
                    peep.card_db.cur.execute(usql, (revlinks[w[name_col].encode('utf-8')].pop(), w['id']))
                except IndexError or KeyError as e:
                    #print(u"no exact match from {} column for {} ".format(name_col, w[name_col]))
                    work.appendleft(w)

        # what remains of work doesn't match anything exactly.
        # now use Levenshtein distance against names.
        print(u"started: {}   by numbers down to: {}   by exact names: {}   "
              u"for set='{}' aka http://magiccards.info/{}/en.html"
              .format(starting_work, intermediate_work, len(work), s, mci))

        for k, l in revlinks.items():
            if not l:
                revlinks.pop(k)
        for w in work:
            scored = []
            for name, link in revlinks.viewitems():
                try:
                    scored.append((name, leven.distance(w['name'].encode('utf-8'),
                                                        name.encode('utf-8'))))
                except UnicodeDecodeError as e:
                    print(u"{} :  -{}-  vs -{}-".format(e, w['name'].encode('utf-8'),
                                                        name.encode('utf-8')))
            if not scored:
                continue
            winner, points = sorted(scored, key=itemgetter(1))[0]
            if points < 5:
                winning_link = revlinks[winner].pop()
                if winning_link:
                    print(u"{}  - close match: (mtginfo)'{}'  ==  '{}'(local) SCORE: {}"
                          .format(winning_link, winner, w['name'], points))
                    peep.card_db.cur.execute(usql, (winning_link, w['id']))
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

    it = peep.card_db.cur.execute("SELECT * FROM cards").fetchall()
    c = 0
    for t in it:
        if t['pic_link']:
            c += 1
    print("before updates of {} entries, counted pic links = {}".format(len(it), c))

    # for testing
    #peep.set_db.cur.execute("UPDATE set_infos SET card_count=0")
    #peep.card_db.con.commit()
    # # # # # # #

    populate_links(card_counts(__db_card_count__.keys()[0]))

        #for k, v in setcodeinfo().viewitems():

        #unsent = [grequests.get(need) for need in checkimages(k, v)]

    it = peep.card_db.cur.execute("SELECT * FROM cards").fetchall()


    return 1

if __name__ == "__main__":
    exit(main())

