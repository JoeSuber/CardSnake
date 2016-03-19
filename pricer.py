
"""
get the price info for all cards from mtgprice.com and cache it into database
1) get web-links-to-price-lists mapped to database set-codes
    a) use release-date and set-name matching, both approximate, perhaps Levenshtien distance
2) use json-encoded price data found on spoiler-list pages to populate a price-list table, adding the local set-code to
    each card-entry
3) make a function that will find prices given an exact local set-code and an approximate card-name-string
"""

import picfinder as pf
import requests
from operator import itemgetter
import json
import grequests
from collections import Counter, deque
import sys

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


def localsets(db=pf.peep.set_db, sql="SELECT code, name, mkm_name, releaseDate FROM set_infos"):
    return [(l[0], l[1].replace('Limited Edition ', '').replace('Classic ', ''), l[2], l[3])
            for l in db.cur.execute(sql).fetchall()]


def correspondence(strips=('_(Foil)')):
    """
    Finds best match among local set-codes for each web-link to a set-pricelist
    external functions: localsets() and mtgdate_map() are used to supply data.
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
    return link_to_setcode


def prices(url):
    """
    returns the json-encoded version of the price info in an mtgprices.com spoiler-list page
    """
    return json.loads(requests.get(url).content.split('$scope.setList =  ')[1].split(';')[0])


def allprices(lmap, db=price_db):
    """
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
    return 1


def price_check(cardname, cardset, foil=False, db=price_db,
                columns=(u'name', u'isFoil', u'fair_price', u'bestVendorBuylistPrice')):
    possibles = db.cur.execute("SELECT {} FROM prices WHERE set_code=?"
                               .format(",".join(columns)), (cardset,)).fetchall()
    return sorted([(p, pf.leven.jaro(cardname, p['name']) + int(int(p['isFoil']) == foil))
                   for p in possibles], key=itemgetter(1), reverse=True)[0]


def main():
    # allprices(correspondence())
    card = price_check('Dragon', '10E', foil=False)
    print card

if __name__ == "__main__":
    exit(main())