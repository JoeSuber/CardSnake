
"""
populate.py is run to initially create and then keep updated a local sqlite database from the .json files
maintained at mtgjson.com. It can do this for any .json files, I think, parsing list and dict
data-types as well as strings and ints.

The updates only update what has changed after the initial run, so should be pretty low overhead

uses: http://mtgjson.com/json/changelog.json to update card db entries that have changed using the SET updater
"""

import os
import path
import json
import sqlite3
import requests
import grequests
from collections import Counter
import time
import gmpy2
from gmpy2 import mpz

DEBUG = True
__author__ = 'suber1'
__sqlext__ = '.sqlite'
__sqlsets__ = os.getcwd() + os.sep + 'mtg_sets' + __sqlext__
__sqlcards__ = os.getcwd() + os.sep + 'mtg_cards' + __sqlext__
__sqlfiles__ = [__sqlsets__, __sqlcards__]
__mtgpics__ = os.getcwd() + os.sep + 'pics'
__needs__ = os.getcwd() + os.sep + 'needs_pic_links.json'
__tackon__ = os.getcwd() + os.sep + 'tack_on_codes.txt'
__mcisite__ = os.getcwd() + os.sep + 'not_local_codes.json'
__notmci__ = os.getcwd() + os.sep + 'not_mci_codes.json'
__jsonsets__ = 'http://mtgjson.com/json/SetCodes.json'
__jsonupdate__ = 'http://mtgjson.com/json/changelog.json'
__one_set__ = 'http://mtgjson.com/json/{}.json'
__req_limit__ = 21          # can the server handle getting pounded by this many?
__test_quant__ = 0          # set to zero for full run
__max_errors__ = 0          # set positive to explore new import data
__last_update__ = os.getcwd() + os.sep + 'last_update.json'
__set_hdr_excluded__ = [u'cards', u'booster']
__cards_hdr_excluded__ = [u'booster', u'foreignNames']
__newness__ = [u"newSetFiles", u"updatedSetFiles"]
__sets_key__ = u'code'
__sets_t__ = 'set_infos'
__cards_key__ = u'id'
__cards_t__ = 'cards'
__cards_dk__ = u'cards'
__types__ = {"<type 'list'>": 'json',
             "<type 'unicode'>": 'TEXT',
             "<type 'str'>": 'TEXT',
             "<type 'float'>": 'REAL',
             "<type 'int'>": 'INTEGER',
             "<type 'dict'>": 'json',
             "<type 'bool'>": 'TEXT',
             "<type 'mpz'>": 'mpz'}



class DBMagic (object):
    """
    DBcolumns = {db_tablename: '''CREATE TABLE db_tablename (column_name1 data_type PRIMARY KEY?,
                                column_name2 data_type, )''', ...}
    user: get the columns from the json entry for a card, or make up your own
    """
    def __init__(self, DBfn=None, DBcolumns=None, DB_DEBUG=False):
        self.DB_DEBUG = DB_DEBUG
        self.DBfn = DBfn
        self.DBcolumns = DBcolumns
        if self.DBfn is None:
            self.DBfn = os.path.join(os.path.expanduser('~'), 'Desktop', "MagicDB", __sqlext__)
            print("WARNING, creating/using a default database: {}".format(self.DBfn))
        if not os.path.isdir(os.path.dirname(self.DBfn)):
            os.makedirs(os.path.dirname(self.DBfn))
        sqlite3.register_converter("json", json.loads)
        sqlite3.register_converter("mpz", gmpy2.mpz)
        sqlite3.register_adapter(list, json.dumps)
        sqlite3.register_adapter(dict, json.dumps)
        sqlite3.register_adapter(mpz, gmpy2.digits)
        self.con = sqlite3.connect(self.DBfn, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.con.row_factory = sqlite3.Row
        self.con.text_factory = sqlite3.OptimizedUnicode
        self.cur = self.con.cursor()
        self.newDB = False
        # check that tables exist. if not, make them
        for t, v in self.DBcolumns.viewitems():
            if not self.cur.execute('''PRAGMA table_info ('{}')'''.format(t)).fetchall():
                self.cur.execute(v)
                self.con.commit()
                print("Created new table: {}".format(t))
                self.newDB = True
            else:
                print("using existing table: {} ".format(t))
            print("in file: {}".format(self.DBfn))
        self.tables = [a[0] for a in
                       self.cur.execute('''SELECT name FROM sqlite_master WHERE type='table' ''').fetchall()]

    def show_columns(self, tablename):
        return [t[1] for t in self.cur.execute('''PRAGMA table_info ('{}')'''.format(tablename)).fetchall()]

    def add_columns(self, tableup, column_map):
        """
        Parameters
        ----------
        tableup: the table to which we are adding columns
        column_map: {'column_foo': sqlite database-type, as string}
                          eg  {'column-name': 'INTEGER', ...}
        """
        present_columns = self.show_columns(tableup)
        for newcol, sql_dtype in column_map.viewitems():
            if newcol not in present_columns:
                self.cur.execute('''ALTER TABLE {} ADD {} {}'''.format(tableup, newcol, sql_dtype))
                if self.DB_DEBUG:
                    print("added column: '{}' of type: '{}' to table: {}".format(newcol, sql_dtype, tableup))
        self.con.commit()

    def add_data(self, data, tbl, key_column=None):
        """
        for populating database with 'official' values.
        for locally changing data, probably should use some other method
        Parameters
        ----------
        data - list of dict cum json objects returned from requests whose wanted keys have been made DB column names
        tbl - db_table to which we add this data
        key - the PRIMARY KEY that the db index is being done on

        Returns
        -------
        Massive side effect = database entry.  Note this isn't an UPSERT, but similar
        """
        n, error_count = -1, 0
        if key_column is None:
            hdrs = self.cur.execute('''PRAGMA table_info ({})'''.format(tbl)).fetchall()
            for h in hdrs:
                if bool(h[5]):
                    key_column = h[1]
                    if self.DB_DEBUG:
                        print("guessing primary key is: {}".format(key_column))

        approved_columns = self.show_columns(tbl)
        for n, line in enumerate(data):
            #print("* {}".format(n))
            line_item = {k: v for k, v in line.viewitems() if k in approved_columns}
            SQL = '''INSERT OR REPLACE INTO {}({}) VALUES({})'''.format(str(tbl), ', '.join(line_item.keys()),
                                                                        ':' + ', :'.join(line_item.keys()))
            try:
                self.cur.execute(SQL, line_item)
            except (sqlite3.OperationalError, sqlite3.InterfaceError) as e:
                error_count += 1
                print
                print("error: {} ***********  {}   len={}  >>> {}    *******".format(error_count, n, len(line_item), e))
                print(SQL)
                print(line_item)
                if error_count > __max_errors__:
                    print("** too many problems to ignore. exiting, harshly **")
                    exit(1)
                continue
        self.con.commit()
        return n, error_count


createstr = '''CREATE TABLE {} ({} TEXT PRIMARY KEY)'''
set_db = DBMagic(DBfn=__sqlsets__,
                 DBcolumns={__sets_t__: createstr.format(__sets_t__, __sets_key__)},
                 DB_DEBUG=DEBUG)
card_db = DBMagic(DBfn=__sqlcards__,
                  DBcolumns={__cards_t__: createstr.format(__cards_t__, __cards_key__)},
                  DB_DEBUG=DEBUG)


def bootup():
    """
    Returns the bases and paths of required items needed to run this thing.
    magiccards.info uses some different set codes for their images, needed for downloads.
    Luckily the json data has those alternate dirnames in there somewhere.
    -------
    """
    homedir = os.getcwd()
    if not os.path.isdir(__mtgpics__):
        os.mkdir(__mtgpics__)
    picdir = __mtgpics__
    return homedir, picdir, \
           [unicode(q.basename()) for q in path.path(homedir).files('*' + __sqlext__)], \
           [unicode(p.basename()) for p in path.path(picdir).dirs()]


def asynch_getter(unsent, groupsize_limit=None, DBG=DEBUG):
    """
    Parameters
    ----------
    unsent: prepared requests objects that are not yet responses
    groupsize_limit: can keep us from spamming web server. 12-at-a-time works

    Returns
    -------
    flat list of 'response' objects from each URL contained in unsent
    """
    if groupsize_limit is None:
        groupsize_limit = len(unsent)
    d = []
    while unsent:
        bunch = []
        groupsize = min(len(unsent), groupsize_limit)
        for x in xrange(groupsize):
            bunch.append(unsent.pop())
        if DBG:
            print("requesting from {} urls".format(groupsize))
        d.extend(grequests.map(bunch))
    return d


def column_parser(datas, exclusions=None, DEBUG=DEBUG):
    """
    called by column_type_parser() now
    Parameters
    ----------
    datas: a list of dicts, possibly derived from downloaded json card data
    exclusions: the keys from datas we don't want in the database

    Returns
    -------
    keys_from_json: Counter object with undesirable keys set to 0 (BUT NOT DELETED!)
    """
    if exclusions is None:
        exclusions = []
        print("using all parsed column names; no exclusions")
    keys_from_json = Counter()
    for i, d in enumerate(datas):
        kks = d.keys()
        for k in kks:
            keys_from_json[k] += 1
    for e in exclusions:
        if e in keys_from_json.keys():
            keys_from_json[e] = 0
    return keys_from_json


def column_type_parser(datas, exclusions=None, types_map=None, DEBUG=DEBUG):
    """
     supply columns & types that need to be added to db from import data
    Parameters
    ----------
    types_map: user created {'python type() output as string': 'sqlite-data-type', ...}

    Returns
    -------
    type_defs: {'column-name': 'appropriate sqlite-data-type', ...}
    """
    if types_map is None:
        types_map = __types__
    if exclusions is None:
        exclusions = []

    type_defs = {}
    usable_columns = [c for c, quant in column_parser(datas, exclusions=exclusions).viewitems() if quant > 0]
    for k in usable_columns:
        for e in datas:
            if k in e.keys():
                try:
                    type_defs[k] = types_map[str(type(e[k]))]
                except KeyError as err:
                    print("{} - is the key, so add to the python-to-sqlite type definitions".format(err))
                    print("PROBLEM: {}".format(e[k]))
                    exit()
                break
    return type_defs


def check_for_updates(update_url, oldfn, need_all=False, DBG=DEBUG):
    """
    Parameters
    ----------
    update_url = url for json-encoded changes to the mtgjson.com data
    oldfn = local file-name for .json file showing the most recent changes incorporated locally

    Returns
    -------
    list of set-codes that need to be updated since the last successful check
    """
    newness = __newness__
    check_codes = []
    try:
        with open(oldfn, mode='rb') as fob:
            old_stuff = json.load(fob)
            most_recent = old_stuff[0][u"version"]
    except Exception as e:
        print("{}".format(e))
        print("couldn't use changes log file ({})".format(oldfn))
        need_all = True
    if need_all:
        most_recent = u"0.0.0"
    old_version = [int(a) for a in most_recent.split(u".")]
    req_new = requests.get(update_url).json()
    if DBG:
        print("*********************** log file stuff ******")
        print("processed: {}    most recent from web: {}".format(most_recent, req_new[0][u'version']))
    i = 0
    for i in xrange(len(req_new)):
        new_version = [int(a) > b for a, b in zip(req_new[i][u'version'].split(u"."), old_version)]
        if any(new_version):
            for tag in newness:
                if tag in req_new[i].keys():
                    check_codes.extend(req_new[i][tag])
        else:  # versions are indexed newest to oldest
            break
    try:
        with open(oldfn, mode='wb') as wob:
            json.dump(req_new, wob)
    except Exception as e:
        print("{}".format(e))
        print("couldn't save the changes log as {}, so updates won't be correct.".format(oldfn))

    check_codes = list(set(check_codes))
    if DBG:
        print("there are {} unprocessed updates from {} ".format(i, update_url))
        print("{} set-codes needed to bring it all up-to-date".format(len(check_codes)))
    return check_codes


def starting_sets(sql_dbs):
    setcodes, needs = [], False
    if len(sql_dbs) != len(__sqlfiles__):
        print("setup: missing required database files: {}".format([f for f in __sqlfiles__ if f not in sql_dbs]))
        print("Getting set codes from: {}".format(__jsonsets__))
        setcodes = requests.get(__jsonsets__).json()
        needs = True
    print("Checking for new or updated set codes at: {}".format(__jsonupdate__))
    return list(set(setcodes + check_for_updates(__jsonupdate__, __last_update__, need_all=needs)))


def info_grubber(unsent_greq, datas=None, tries=10):
    if datas is None:
        datas = []
    fails = []
    while tries:
        fails = []
        for n, d in enumerate(asynch_getter(unsent_greq, groupsize_limit=__req_limit__)):
            if d.status_code == 200:
                datas.append(d.json())
            else:
                fails.append(d.url)
        if fails:
            print("< {} > retrying {} urls ".format(tries, len(fails)) + "".join('*' * tries))
            time.sleep(.4)
            tries -= 1
            unsent_greq = [grequests.get(u) for u in fails]
        else:
            tries = 0
    return datas, fails


def xando(setcodes, mk='-x'):
    """
    use each setcode only once, so if & only if an 'ABC-x' version exists, remove the 'ABC' version
    """
    keepers, stripped, stumpys = [], [], []
    for x in setcodes:
        if mk in x:
            keepers.append(x)
            stripped.append(x.split(mk)[0])
        else:
            stumpys.append(x)
    for y in stumpys:
        if y not in stripped:
            keepers.append(y)
    return keepers


def deckify(dats):
    """ add a column 'code' to make set queries a bit easier
        # put all cards from all sets into one flat list"""
    deck = []
    for e in dats:
        for cardline in e[__cards_dk__]:
            cardline.setdefault(u'code', e[__sets_key__])
            deck.append(cardline)
    return deck


def main():
    homedir, picdir, sqldbs, picsets = bootup()

    if (DEBUG and (len(sqldbs) == len(__sqlfiles__))):
        print("using existing sqlite db fns: {}".format(sqldbs))

    urls = [__one_set__.format(s) for s in xando(starting_sets(sqldbs))]
    unsent = [grequests.get(u) for u in urls[:(__test_quant__ or len(urls))]]

    datas, fails = info_grubber(unsent, tries=8)

    for p in fails:
        print("url didn't play nice: {}".format(p))

    # aggregate all the columns (while assigning their data-types) for each data-set
    columns_for_sets = column_type_parser(datas, exclusions=__set_hdr_excluded__)
    deck = deckify(datas)
    columns_for_cards = column_type_parser(deck, exclusions=__cards_hdr_excluded__)

    if DEBUG:
        print("'set_infos' columns to update: {}".format(columns_for_sets))
        print("'cards' columns to update: {}".format(columns_for_cards))

    # adding the approved column-headers to existing tables (if not already present)
    set_db.add_columns(set_db.tables[0], columns_for_sets)
    card_db.add_columns(card_db.tables[0], columns_for_cards)

    # should be ready to add the data to local database!
    a, b = card_db.add_data(deck, card_db.tables[0], key_column=__cards_key__)
    print("processed cards: {}, import errors: {}".format(a+1, b))
    c, d = set_db.add_data(datas, set_db.tables[0], key_column=__sets_key__)
    print("processed sets: {}, import errors: {}".format(c+1, d))
    return 1

if __name__ == "__main__":
    exit(main())