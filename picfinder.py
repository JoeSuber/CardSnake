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

import populate as peep
import requests, grequests
from collections import deque, defaultdict, Counter
import Levenshtein as leven
from operator import itemgetter
from itertools import izip
import os
import json
import sys
reload(sys).setdefaultencoding("utf8")

__db_pic_col__ = {'pic_path': 'TEXT'}
__db_link__ = {'pic_link': 'TEXT'}
__db_card_count__ = {'card_count': 'INTEGER'}
__mci_front__ = 'http://magiccards.info/scans/en/'
__mci_jpg__ = __mci_front__ + '{}/{}.jpg'
__mci_set_stub__ = "http://magiccards.info/{}/en.html"
__mci_parser__ = '<td><a href="/{}/en/'
__mci_sitemap__ = 'http://magiccards.info/sitemap.html'

# json data has some strangeness in it:
# oddities will need to be matched to pics on different pages than 'normal' cards
# oddities are included in some card sets along with normal cards. key=='layout'...
oddities = ["phenomenon", "plane", "token", "scheme", "vanguard"]
# these sets include duplicate numbers, so matching by name only is required:
numberskip = ["CPK", "9ED", "8ED", "CST"]
# these keys need links from these vals in addition to the json given 'magicCardsInfoCode'
extrastuff = {"9ED": "9eb", "8ED": "8eb"}


def setcodeinfo():
    """
    returns {'official' set code: magicCardsInfo code, 'ISD': 'isd', ...}
    """
    return {k: v for k, v in peep.set_db.cur.execute("SELECT code, magicCardsInfoCode FROM {}"
                                                     .format(peep.__sets_t__, )).fetchall()}


def linkup(line):
    # in: '    <td><a href="/isd/en/2.html">Angel of Flight Alabaster</a></td>'
    # out: ('http://magiccards.info/scans/en/isd/2.jpg', 'Angel of Flight Alabaster')
    a, b = line.split('.html">')
    ms, num = a.split('    <td><a href="/')[1].split('/en/')
    name = b.split('</a>')[0].strip()
    return __mci_jpg__.format(ms, num), name


def setlist_links(mci_setcode):
    """
    mci_setcode: string from database ie 'isd'
    return: links for all images in set {'Name of Card': 'http://address-to-image.jpg', ...}
    """
    ri = requests.get(__mci_set_stub__.format(mci_setcode)).iter_lines()
    return dict([linkup(i) for i in ri if __mci_parser__.format(mci_setcode) in i])


def mci_sitemap_parser(sm=__mci_sitemap__, ):
    # mci set-codes are different than standard 3-all-caps, but often similar.
    # the json data for a newly released set often doesn't include the mci-set-code
    # this gets a list of all the possible mci codes.
    r = requests.get(sm)
    MAIN_LINE = False
    mci_codes = list()
    if r.status_code != 200:
        print("status code: {} ...No sitemap page from: {}".format(r.status_code, sm))
        return []
    for kk in r.iter_lines():
        if MAIN_LINE:
            for s in kk.split('<small style="color: #aaa;">'):
                mci_codes.append(s.split('</small></li><')[0])
            return mci_codes[1:]

        if '<small style="color: #aaa;">en</small></h2>' in kk:
            MAIN_LINE = True
    return []


def card_counts(counter_col):
    """
    return {set-code: mci-code, ...} for sets containing any cards missing a valid local image path
    """
    # add some straggler mci codes if possible
    mci_codes_from_sitemap = mci_sitemap_parser()
    for code, mci in setcodeinfo().viewitems():
        if mci is None:
            if code.lower() in mci_codes_from_sitemap:
                print("Using magiccards.info sitemap to add '{}' to setcodes".format(code.lower()))
                peep.set_db.cur.execute("UPDATE {} SET magicCardsInfoCode=(?) WHERE code=(?)"
                                        .format(peep.__sets_t__), (code.lower(), code))
    peep.set_db.con.commit()

    # just check them all (in a set) if any are missing? seems ok
    needs_links = {}
    for kkk, mci in setcodeinfo().viewitems():
        if mci:
            allhits = peep.card_db.cur.execute("select code, pic_path from {} WHERE code=?"
                                               .format(peep.__cards_t__), (kkk,)).fetchall()
            for a in allhits:
                if not a['pic_path']:
                    needs_links.update({kkk: mci})
                    break
                else:
                    if not os.path.isfile(a['pic_path']):
                        needs_links.update({kkk: mci})
                        break
    return needs_links


def num_from_urls(urls, num, layout):
    # num is actually text
    # must split it out to avoid finding '1' in '100'
    for u in urls:
        #print "urls u:", u
        if num == u.split('/')[-1].split('.jpg')[0].strip():
            return u
    return False


def populate_links(setcodes):
    """
    setcodes = {three-character-all-caps-json-given-set-code: magiccards.info set-code, ...}
    """
    sql = '''SELECT id, name, imageName, number, layout, code from {} where code=?'''.format(peep.__cards_t__)
    usql = '''UPDATE {} SET pic_link=? WHERE id=?'''.format(peep.__cards_t__)
    oddballs = defaultdict(list)
    with open("local_mias", 'wb') as fob:
        fob.write("list of unmatched local database items:\n")

    for s, mci in setcodes.viewitems():
        if mci is None:
            print("ATTENTION: {} has no magiccards.info code, and will get no pics from there!".format(s))
            continue

        # each chunk of work is determined by the official setcode, but won't go without mci codes
        work = deque(peep.card_db.cur.execute(sql, (s,)).fetchall())

        for x in xrange(len(work)):
            w = work.pop()
            if w['layout'] in oddities:
                oddballs[w['layout']].append({k: w[k] for k in w.keys()})
            else:
                work.appendleft(w)

        starting_work = len(work)
        links = setlist_links(mci)
        if s in extrastuff.keys():
            links.update(setlist_links(extrastuff[s]))
        # links are from web, work is from local
        if len(links) != starting_work:
            msg = u"{} aka {}: has {} web-based, but {} local items\n".format(s, mci, len(links), starting_work)
            with open("local_mias", 'a+') as fob:
                fob.write(msg)

        # try to match by card number in url, and local, .json-given 'number'
        for x in xrange(len(work)):
            w = work.pop()
            if w['code'] in numberskip:
                work.appendleft(w)
                continue
            num, result = w['number'], False
            if num:
                result = num_from_urls(links.keys(), num.strip(), w['layout'])
            if result:
                peep.card_db.cur.execute(usql, (result, w['id']))
                links.pop(result)
            else:
                work.appendleft(w)

        #print(u"numbermatching: of {} db entries, {} remain{} for set='{}' aka http://magiccards.info/{}/en.html"
        #     .format(starting_work, len(work), u's' if len(work) == 1 else u'', s, mci))

        intermediate_work = len(work)

        # try matching to href links by exact card-names in database
        revlinks = defaultdict(list)
        for k, v in links.viewitems():
            revlinks[v.encode('utf-8')].append(k)
        for name_col in ['name']:       # used to match against 'imageName' as well. might go back to that.
            for x in xrange(len(work)):
                w = work.pop()
                try:
                    peep.card_db.cur.execute(usql, (revlinks[w[name_col].encode('utf-8')].pop(), w['id']))
                    continue
                except IndexError:
                    print(u"set {} has no remaining exact match for: '{}'".format(s, w[name_col].encode('utf-8')))
                    # remove the key since it has no links remaining
                    revlinks.pop(w[name_col].encode('utf-8'))
                except KeyError:
                    print(u"{}: {} has No Key-name for: '{}'".format(x, s, w[name_col].encode('utf-8')))
                work.appendleft(w)

        msg = u"started: {}   by numbers down to: {}   by exact names: {}  " \
              u"for set='{}' aka http://magiccards.info/{}/en.html \n"\
            .format(starting_work, intermediate_work, len(work), s, mci)
        with open("local_mias", 'a+') as fob:
            fob.write(msg)

        # clear out empty entries
        for k, l in revlinks.items():
            if not l:
                revlinks.pop(k)

        # what remains of work doesn't match anything exactly.
        # now use Levenshtein distance against names.
        leven_msgs = []
        for x in xrange(len(work)):
            w = work.pop()
            scored = []
            msg = ""
            for name in revlinks.viewkeys():
                try:
                    scored.append((name, leven.distance(w['name'].encode('utf-8'), name)))
                except UnicodeDecodeError as e:
                    print(u"{} :  -{}-  vs -{}-".format(e, w['name'].encode('utf-8', errors='replace'), name))
                    scored.append((name, leven.distance(w['name'].encode('utf-8', errors='replace'), name)))
            if not scored:
                work.appendleft(w)
                continue
            winner, points = sorted(scored, key=itemgetter(1))[0]
            if (points < 5) and revlinks[winner]:
                winning_link = revlinks[winner].pop()
                msg = u"{}  - close enough match: (mtginfo)'{}'  ==  '{}'(local) SCORE: {}"\
                    .format(winning_link, winner, w['name'], points)
                peep.card_db.cur.execute(usql, (winning_link, w['id']))
            else:
                work.appendleft(w)
            if msg:
                print(msg)

        # looks like the end of the line. Record remaining work.
        if work:
            msg = u"for set: {} aka {}, after all efforts, {} of {} items remain:"\
                   .format(s, mci, len(work), starting_work)
            print(msg)
            with open("local_mias", 'a+') as fob:
                fob.write(msg + u"\n")
        for n, w in enumerate(work):
            msg = u"{}: {} | {} | {} | {}".format(n+1, s, w['name'], w['number'], w['id'])
            print(msg)
            with open("local_mias", 'a+') as fob:
                fob.write(msg + u"\n")

    with open("oddballs.json", 'wb') as odd:
        json.dump(oddballs, odd)

        #todo: use magiccards.info 'extras' page to do more final matching
        # http://magiccards.info/extras.html

    peep.card_db.con.commit()


def download_pics(db=peep.card_db, fs_stub=peep.__mtgpics__, attempt=100, skip=None):
    """
    to avoid blasting the web-server with grequests, check for valid local pictures a few at a time.
    Get the missing pics using the pic_link.  Update the database.
    """
    if skip is None:
        skip = []
    sql = '''SELECT id, name, pic_path, pic_link, code from {}'''.format(peep.__cards_t__)
    usql = '''UPDATE {} SET pic_path=? WHERE id=?'''.format(peep.__cards_t__)
    work = db.cur.execute(sql).fetchall()
    real_work = []
    needed_ids, needed_local_paths, needed_links, file_exists = [], [], [], []
    new_dirs = Counter()

    # first filter out some causes of errors
    for w in work:
        # are we supposed to skip it (bad link already tried, etc)?
        if w['id'] in skip:
            continue
        # is there a link?
        if not w['pic_link']:
            # print ("NO PIC LINK: {} of {}".format(w['name'], w['code']))
            continue
        # is the required file present and not empty?
        if w['pic_path']:
            prospect = os.path.join(fs_stub, w['pic_path'])
            if os.path.isfile(prospect) and os.stat(prospect).st_size > 10:
                continue
        # if none of above, add to real_work
        real_work.append(w)

    quant_left = len(real_work)
    # go to work on (some portion of) real work
    for w in real_work[:min(attempt, quant_left)]:
        # windows compatibility hack (win OS hates the string 'CON'):
        tag = ''
        if (w['code'] == 'CON') and ('nt' in os.name):
            tag = 'win'
        # preserve unique origination information in the filename:
        q = os.path.join(fs_stub, w['code'] + tag, "".join(w['pic_link'].split("/")[-2:]))
        # in case the database held path was deleted, but localpic file is still here...
        if os.path.isfile(q) and os.stat(q).st_size > 10:
            file_exists.append(True)
        else:
            file_exists.append(False)
        needed_local_paths.append(q)
        needed_ids.append(w['id'])
        needed_links.append(w['pic_link'])
        new_dirs[os.path.join(fs_stub, w['code'] + tag)] += 1

    # check that all filenames are unique
    try:
        assert(len(set(needed_local_paths)) == len(needed_local_paths))
    except AssertionError:
        # show duplicate paths, ie one picture path assigned to multiple ids
        for p, l, i in zip(needed_local_paths, needed_links, needed_ids):
            idxs = [i for i, s in enumerate(needed_local_paths) if p == s]
            if len(idxs) > 1:
                print("  BAD:   picture paths assigned to multiple ids     *********")
                for x in idxs:
                    print needed_local_paths[x], " ", needed_links[x], " ", needed_ids[x]
        exit(1)

    # make new directories
    for dir in new_dirs.keys():
        if not os.path.isdir(dir):
            os.makedirs(dir)

    # prepare & send work to grequests
    reqs = (grequests.get(u) for u in needed_links)
    resps = grequests.map(reqs)

    successes = 0

    # take responses and turn into binary image files, record success in database by recording fs path
    for num, (lp, dbid, rsp, here) in enumerate(izip(needed_local_paths, needed_ids, resps, file_exists)):
        if rsp.status_code == 200:
            try:
                if not here:
                    with open(lp, 'wb') as fob:
                        for chunk in rsp.iter_content(1024):
                            fob.write(chunk)
                a, b = lp.split(os.path.sep)[-2:]
                db.cur.execute(usql, (os.path.join(a, b), dbid))
                successes += 1
            except Exception as e:
                print(e)
                print("{} had good response, but is still screwy!".format(lp))
        if rsp.status_code == 404:
            skip.append(dbid)

    db.con.commit()
    print("{} more pics needed".format(quant_left-successes))
    return skip, quant_left - successes


def main():
    peep.card_db.add_columns(peep.__cards_t__, __db_pic_col__)
    peep.card_db.add_columns(peep.__cards_t__, __db_link__)
    peep.set_db.add_columns(peep.__sets_t__, __db_card_count__)
    #print peep.card_db.show_columns(peep.__cards_t__)
    it = peep.card_db.cur.execute("SELECT * FROM cards").fetchall()

    # for testing populate_links
    #peep.set_db.cur.execute("UPDATE set_infos SET card_count=0")
    #peep.card_db.con.commit()
    # # # # # # #

    populate_links(card_counts(__db_card_count__.keys()[0]))
    trying = 100
    remains = len(it)
    baddies = []
    print("attempting to get {} per download run:".format(trying))
    while remains > 0:
        bad, remains = download_pics(attempt=trying, skip=baddies)
        if bad:
            baddies.append(bad)


    for bad in baddies:
        for i in it:
            if i['id'] == bad:
                print("404, bad link: {} - {}".format(i['name'], i['pic_link']))

    return 1

if __name__ == "__main__":
    exit(main())