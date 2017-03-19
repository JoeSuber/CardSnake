#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
"""
get the price info for all cards from mtgprice.com and cache it into local database
1) get web-links-to-price-lists mapped to existing local database set-codes.
    a) for robustness, use release-date and set-name matching, both approximate, by Levenshtien distance
2) use json-encoded price data found on spoiler-list pages to populate a price-list table, adding the local set-code to
    each card-entry
3) assign mtgprice.com 'cardID' (for foils and regular cards) to local 'id' so that price data is quickly accessed.
    a) Use iterative winnowing of prospective matches and local names (within set-codes) to avoid mis-assignments.
"""

import picfinder as pf
import requests
import grequests
from operator import itemgetter
import json
import time
from collections import defaultdict

# time required between subsequent price scrapes:
HOUR_DELAY = 2.0

price_db = pf.peep.DBMagic(DBfn=pf.peep.__sqlcards__,
                           DBcolumns={'prices': pf.peep.createstr.format('prices', 'cardId')},
                           DB_DEBUG=True)

"""
[{u'absoluteChangeSinceYesterday': 0.0, u'setName': u'10th Edition (Foil)', u'name': u'Abundance',
u'fair_price': 31.98, u'lowestPriceVendor': u'StrikeZone', u'isFoil': True, u'bestVendorBuylistPrice': u'20.0',
u'manna': u'2GG', u'fullImageUrl': u'http://s.mtgprice.com/sets/10th_Edition/img/Abundance.full.jpg',
u'setUrl': u'/spoiler_lists/10th_Edition_(Foil)', u'countForTrade': 0, u'rarity': u'R',
u'url': u'/sets/10th_Edition_Foil/Abundance', u'bestVendorBuylist': u'StrikeZone',
u'percentageChangeSinceOneWeekAgo': 0.0, u'cardId': u'Abundance10th_Edition_FoiltrueNM-M',
u'percentageChangeSinceYesterday': 0.0, u'lowestPrice': u'31.98', u'absoluteChangeSinceOneWeekAgo': 0.0,
u'color': u'G', u'quantity': 0},
{u'absoluteChangeSinceYesterday': 0.0, ...}
"""


def mtg_seturl(setname, front='http://www.mtgprice.com/spoiler_lists/'):
    return front + setname


def mtgdate_map(url='http://www.mtgprice.com/magic-the-gathering-prices.jsp'):
    """
    Returns: dict keyed by links to each set-price-list, with value-tuple of:
            (display name, is-it-Foil?-boolean, date-code-string in database year-month-day format)
    """
    splt1 = '<a href ="/spoiler_lists/'
    a, b, c = '">', '</a> </td><td>', '</td></tr><'
    foil_str = " (Foil)"
    mp = {}
    for l in requests.get(url).content.split(splt1)[1:]:
        FOIL = False
        kk, rest = l.split(a)[:2]
        name, rest = rest.split(b)
        if foil_str in name:
            name = name.split(foil_str)[0]
            FOIL = True
        m, d, y = rest.split(c)[0].split('/')
        mp[mtg_seturl(kk)] = (name, FOIL, y + '-' + m + '-' + d)
    print("mtgdate_map() reports there are {} price-page-links at {}".format(len(mp), url))
    return mp


def async_prices(sites):
    """ sites is the dict output of mtgdate_map()  """
    bad_objs, bad_explanations = [], []

    def handler(quest_obj, exception):
        bad_objs.append(quest_obj)
        bad_explanations.append(exception)

    print("timer start: {}".format(time.time()))

    rs = (grequests.get(u) for u in sites.keys())

    pricelist = grequests.map(rs, exeption_handler=handler)

    return pricelist, bad_objs, bad_explanations


def localsets(db=pf.peep.set_db, sql="SELECT code, name, mkm_name, releaseDate FROM set_infos"):
    """ hack to allow easier matching of local set-names to mtgprices names"""
    return [(l[0], l[1].replace('Limited Edition ', '').replace('Classic ', ''), l[2], l[3])
            for l in db.cur.execute(sql).fetchall()]


def recent_checked(unchecked_codes, current_time=None, hour_delay=HOUR_DELAY, db=pf.peep.card_db):
    """ filter out the items returned by correspondence() that have been too recently checked"""
    if 'last_update' not in db.show_columns('cards'):
        return unchecked_codes
    if current_time is None:
        current_time = time.time()
    delay = hour_delay * 3600
    checked_codes = {}
    for kk, line in unchecked_codes.viewitems():
        avg = delay + 1
        c = line[0]
        times = [current_time - t[0] for t in
                 db.cur.execute("SELECT last_update FROM cards WHERE code=?", (c[0][0], )).fetchall() if t[0]]
        if times:
            avg = sum(times) / float(len(times))
        if avg > delay:
            checked_codes[kk] = line
        else:
            print("{} ({}) was checked within the last {} hours".format(c[0][1], c[0][0], hour_delay))
    return checked_codes


def correspondence():
    """
    external functions: localsets() and mtgdate_map() are used to supply data.
    Uses name, release year, and then full release date to score the similarity of a set-code to its mtgprices name.
    Returns: dict of {web-link to a set-pricelist: best match among local set-codes, ...}
    """
    locs = localsets()
    link_to_setcode = {}
    for lnk, (dname, foil, rdate) in mtgdate_map().viewitems():
        year = rdate.split('-')[0]
        best = sorted([(l, pf.leven.jaro(str(dname), str(l[1])) +
                           pf.leven.jaro(str(rdate), str(l[3])) +
                           int(str(year) == str(l[3].split('-')[0])))
                      for l in locs], key=itemgetter(1), reverse=True)
        link_to_setcode[lnk] = (best[0], foil)
    return recent_checked(link_to_setcode)


def prices(url):
    """
    returns the json-encoded version of the price info underneath an mtgprices.com spoiler-list page
    """
    try:
        return json.loads(requests.get(url).content.split('$scope.setList =  ')[1].split(";\n")[0])
    except:
        # rarely the page data is missing even when requests returns something saying its okay
        print("PROBLEM WITH DATA AT: {}  \n".format(url))
        return []


def allprices(lmap, db=price_db):
    """
    create or update the local price-info database using all the scraped up info
    lmap: [{link-to-spoiler-list: set-matching info, including setcode}, ...]
    db: the database connection object to be written to
    """
    biglist = []
    for item_num, (link, info) in enumerate(lmap.viewitems()):
        pricelist = prices(link)
        for card in pricelist:
            card['set_code'] = info[0][0][0]
        print("{:3}: adding {} items for {}".format(item_num, len(pricelist), link))
        biglist.extend(pricelist)
    print("attempting to commit {} price lines".format(len(biglist)))
    db.add_columns('prices', pf.peep.column_type_parser(biglist))
    db.add_data(biglist, 'prices', key_column=u'cardId')
    print("Done!")
    return len(biglist)


def name_check(cardname, possibles=None, foil=False,):
    """
    cardname: any string-name approximately thought to be in a given set-of-cards
    possibles: list of sqlite return tuples likely from a set-code-query of price-data
    foil: False==plain-price, True==foil-price

    Returns
    -------
    the best match according to Levenshtein.jaro string similarity and "foilness."
    2.0 is perfect, anything less than 1.0 doesn't match the foil criteria. 1.7 is suspect
    also returns the remaining unmatched items in the 'possibles' list
    """
    if not possibles:
        return None, []
    try:
        the_list = sorted([(p, pf.leven.jaro(unicode(cardname),
                                             unicode(p['name'])) + int(int(p['isFoil'] or 0) == foil))
                           for p in possibles], key=itemgetter(1), reverse=True)
    except TypeError as err:
        print(err)
        print("trouble with? -> {}, {}".format(cardname, type(cardname)))
        exit(12)

    if len(the_list) > 1:
        return the_list[0], [p[0] for p in the_list[1:]]

    return the_list[0], []


def set_has_foils(setcode, default_linelen=2, db=price_db):
    """ used for knowing when a row-entry is complete, and thus can be removed from prospects"""
    return default_linelen + int(any([int(f[0] or 0)
                                      for f in db.cur.execute("SELECT isFoil FROM prices WHERE set_code=?",
                                                             (setcode, )).fetchall()]))


def recently_checked(current_time, last_check, hours_to_ignore=HOUR_DELAY):
    """both times are in seconds-since-the-epoch float format"""
    return ((current_time - (last_check or 0))/3600.0) < hours_to_ignore


def multi_price(cardset, dbp=price_db, dbid=pf.peep.card_db, DEBUG=False):
    """
    By doing the matching on a set-by-set basis and first winnowing down to the hard-to-match items, the overall results
    are far more accurate than attempting to match all against all while using the needed approximate string matching.
    Parameters
    ----------
    cardset: the 3-letter all-caps set-code imported with mtgjson.com data and used in the local cards_db
    dbp: the price database scraped from mtgprices.com spoiler pages, with that cardset already added to each entry
    dbid: the cards_db that holds the local mtgjson derived data and is keyed by a sha1 hash ('id')

    Side-Effects:
    -------
    attaches appropriate entries (regular & foil 'cardId' from mtgprices.com) to 'id' in cards_db.
    This will allow for faster and more accurate access to price data by the simple local 'id' of a card.
    Also adds the date of the last price change/check in "seconds since the epoch" float style.
    """
    columns = (u'cardId', u'name', u'isFoil')
    possibles = dbp.cur.execute("SELECT {} FROM prices WHERE set_code=?"
                                .format(",".join(columns)), (cardset,)).fetchall()
    date = time.time()
    if 'last_update' in dbid.show_columns('cards'):
        local_ids = {l['id']: l['name'] for l in
                     dbid.cur.execute("SELECT id, name, last_update FROM cards WHERE code=?", (cardset,)).fetchall()
                     if not recently_checked(date, l['last_update'])}
    else:
        local_ids = {l['id']: l['name'] for l in
                     dbid.cur.execute("SELECT id, name FROM cards WHERE code=?", (cardset, )).fetchall()}

    matchlevels = [1.99, 1.93, 1.88, 1.84, 1.813, 1.80, 1.79, 1.74, 1.695]
    leveltracker = {}
    pricelines = defaultdict(dict)
    line_items_constant = set_has_foils(cardset)
    rk, fk, lup = 'regular_price_info', 'foil_price_info', 'last_update'

    # first find the perfect name matches, then proceed down the match level steps, winnowing the possibilities:
    for level in matchlevels:
        if DEBUG:
            print("{} local and {} possibles in {} before doing matchlevel: {}"
                  .format(len(local_ids), len(possibles), cardset, level))
        if (not possibles) or (not local_ids):
            break
        for idk, idname in local_ids.viewitems():
            # plain card prices
            regular_match, possibles = name_check(idname, possibles=possibles, foil=False)
            if not regular_match:
                break
            if regular_match[1] > level:
                pricelines[idk].update({rk: regular_match[0][0], lup: date})
                if DEBUG:
                    leveltracker[idk] = (level, regular_match[1])
            else:
                possibles.append(regular_match[0])
            # foil card prices
            foil_match, possibles = name_check(idname, possibles=possibles, foil=True)
            if not foil_match:
                break
            if foil_match[1] > level:
                pricelines[idk].update({fk: foil_match[0][0], lup: date})
                if DEBUG:
                    leveltracker[idk] = (level, foil_match[1])
            else:
                possibles.append(foil_match[0])

        # loop back over only the incomplete local items on the next matchlevels step
        local_ids = {idk: idname for idk, idname in local_ids.viewitems() if len(pricelines[idk]) < line_items_constant}

    # test it!        if best[0][1] > 1.:
    if DEBUG:
        print("Only showing items below matchlevel = {}".format(matchlevels[1]))
        for kk, vv in pricelines.viewitems():
            if kk not in leveltracker.keys():
                localname = dbid.cur.execute("SELECT name FROM cards WHERE id=?", (kk, )).fetchone()
                print("***!!!***  {}   - not matched even at:  {}".format(localname[0], matchlevels[-1]))
                continue
            if leveltracker[kk][1] < matchlevels[1]:
                price_id, price_name = '', ('', 0)
                foil_id, foil_name = '', ('', 0)
                linekeys = vv.keys()
                if rk in linekeys:
                    price_id = vv[rk]
                    price_name = dbp.cur.execute("SELECT name, fair_price FROM prices WHERE cardId=?", (price_id, )).fetchone()
                if fk in linekeys:
                    foil_id = vv[fk]
                    foil_name = dbp.cur.execute("SELECT name, fair_price FROM prices WHERE cardId=?", (foil_id, )).fetchone()
                localname = dbid.cur.execute("SELECT name FROM cards WHERE id=?", (kk, )).fetchone()
                #print "local: {}   reg: {}    foil: {}".format(localname, price_name, foil_name)
                print localname[0], ' | ', price_name[0], ' | ', foil_name[0], " -{}-  "\
                    .format('|*<<|*|>>*|' if price_name[0] != foil_name[0] else '-----'), "  ", leveltracker[kk]

    # prepare pricelines dict for database entry by making it a list of dict
    new_datas = []
    for kk, vv in pricelines.viewitems():
        if len(vv):
            line = {'id': kk}
            line.update(vv)
            new_datas.append(line)
    return new_datas


def single_price(local_id, foil=False, dbid=pf.peep.card_db, dbp=price_db, price_columns=None):
    if not price_columns:
        price_columns = 'name, fair_price, bestVendorBuylistPrice'
    if foil:
        column = 'foil_price_info'
    else:
        column = 'regular_price_info'
    price_id = dbid.cur.execute("SELECT {}, last_update FROM cards WHERE id=?"
                                .format(column), (local_id, )).fetchone()
    return dbp.cur.execute("SELECT {} FROM prices WHERE cardId=?".format(price_columns), (price_id[0], )).fetchone(), \
           price_id['last_update']


def main(dbid=pf.peep.card_db, mainDEBUG=False):
    # scrape the card prices and assign a local set code to each card-price-line
    allprices(correspondence())

    # assign card-price-cardId to local json-card-data so that prices can be looked up quickly using 'id'
    big_data = []
    for s_code in [s[0] for s in pf.peep.set_db.cur.execute("SELECT code FROM set_infos").fetchall()]:
        old_len = len(big_data)
        if mainDEBUG:
            print("\n up next: {}".format(s_code))
            inq = str(raw_input("[q] to quit! [s] to skip! >>> ")).strip()
            if inq == 'q':
                break
            if inq == 's':
                continue
            if len(inq) == 3:
                s_code = inq
        big_data.extend(multi_price(s_code, DEBUG=mainDEBUG))
        update_size = len(big_data) - old_len
        if update_size:
            print("set: {} had {} updated price-lines".format(s_code, update_size))

    # add columns if needed, then add the data
    if big_data:
        dbid.add_columns('cards', pf.peep.column_type_parser(big_data))
        dbid.add_data(big_data, 'cards', key_column='id')


if __name__ == "__main__":
    exit(main())