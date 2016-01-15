#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
some db-examination/debug stuff for pasting into ipython console and general convenience
"""
import sys
reload(sys).setdefaultencoding("utf8")
import populate as peep
import pprint


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

if __name__ == "__main__":
    pprint.pprint(cols())

