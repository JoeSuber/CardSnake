#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
generate some dct data if needed. Use it to help determine the most similar images to a captured image.

run populate first, then picfinder, then run orientation and wait a few minutes while new dcts are added to database
"""
import sys
reload(sys).setdefaultencoding("utf8")
import populate as peep
import os
import gmpy2
from gmpy2 import mpz
import cv2
import numpy as np
from collections import defaultdict, Counter, deque

__RAT__ = 0.80  # image height = __RAT__* width. This mostly puts top-image-bottom-border at art-line

#peep.card_db.cur.execute("DROP TABLE orient")

orient_db = peep.DBMagic(DBfn=peep.__sqlcards__,
                         DBcolumns={'orient': peep.createstr.format('orient', peep.__cards_key__)},
                         DB_DEBUG=True)

orient_db.add_columns('orient', {'top_dct': 'TEXT', 'bot_dct': 'TEXT', 'picpath': 'TEXT', 'face': 'INTEGER'})


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
    # joins unique part of path to local stub.
    cardmap = {}
    for line in peep.card_db.cur.execute("SELECT id, name, code, pic_path from cards").fetchall():
        #print("fs={}   picpath={}".format(fs, line['pic_path']))
        if line['pic_path']:
            cardmap[line['id']] = os.path.join(fs, line['pic_path'])
    return cardmap


def needed_faces(cardmap, examine_zeros=False):
    """
    filter cardmap to include only items that need examination for faces.
    defaults to only examining 'null' valued, new items, not zeroes.
    """
    needed = {}
    for id in cardmap.viewkeys():
        card_has_face = orient_db.cur.execute("SELECT face FROM orient WHERE id=?", (id,)).fetchone()[0]
        if card_has_face is None or (examine_zeros and not card_has_face):
            needed[id] = cardmap[id]
    return needed


def find_faces(cardmap, scale=1.35, min_neighbor=4):
    """
    Parameters
    ----------
    cardmap: {database id: local/path/to/pic, ...}

    Returns
    -------
    counter object showing the quantity of examined pics with a given number of faces detected.
    side-effect: database column 'face' gets updated with quantity of faces found.
    """
    facecount = Counter()
    if not cardmap:
        return facecount
    print("face finder will examine {} pictures, using scale={} minNeighbors={}"
          .format(len(cardmap), scale, min_neighbor))
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    for n, (id, cardpath) in enumerate(cardmap.viewitems()):
        faces = face_cascade.detectMultiScale(cv2.equalizeHist(cv2.imread(cardpath, cv2.IMREAD_GRAYSCALE)),
                                              scaleFactor=scale, minNeighbors=min_neighbor)
        print("{}: {} -- {}".format(n, len(faces), faces))
        facecount[len(faces)] += 1
        orient_db.cur.execute("UPDATE orient SET face=(?) WHERE id=(?)", (len(faces), id))
    orient_db.con.commit()
    return facecount


def add_dct_data(cardpaths):
    """
    sock away top and bottom dcts of pics as persistent 64-bit int
    """
    datas = []
    allin = orient_db.cur.execute("SELECT * from orient").fetchall()
    qneed = [a['picpath'] is None for a in allin].count(True)
    print("dct-database is missing data for {} of {} possible rows.".format(qneed, len(cardpaths)))
    if qneed:
        for k, v in cardpaths.viewitems():
            shortpath = os.path.sep.join(v.split(os.path.sep)[-2:])
            if all([a['picpath'] != shortpath for a in allin]):
                #print("+ {}".format(shortpath))
                im = cv2.equalizeHist(cv2.imread(v, cv2.IMREAD_GRAYSCALE))
                height, width = im.shape[:2]
                line = {'id': k, 'picpath': shortpath, 'top_dct': gmpy2.digits(dct_hint(im[:width*__RAT__, :width])),
                        'bot_dct': gmpy2.digits(dct_hint(im[height-width*__RAT__:height, :width]))}
                datas.append(line)
    print("adding {} new lines of data to a previous {} lines".format(len(datas), len(allin)))
    if datas:
        orient_db.add_data(datas, 'orient', 'id')
        print("committed!")
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


def getdcts(only_faces=False):
    """
    takes the dry, text version of the dcts stored in the database and hydrates them into mpz() objects
    """
    dcts = orient_db.cur.execute("SELECT top_dct, bot_dct, id, face FROM orient").fetchall()
    ups = [gmpy2.mpz(up['top_dct']) for up in dcts]
    downs = [gmpy2.mpz(down['bot_dct']) for down in dcts]
    ids = [i['id'] for i in dcts]
    if only_faces:
        ups, downs, ids = deque(ups), deque(downs), deque(ids)
        for line in dcts:
            u, d, i = ups.pop(), downs.pop(), ids.pop()
            if line['face']:
                ups.appendleft(u)
                downs.appendleft(d)
                ids.appendleft(i)
        ups, downs, ids = list(ups), list(downs), list(ids)
    return ups, downs, [i['id'] for i in dcts]


def npydcts():
    """
    if we want numpy's version of unsigned, 64-bit integers to represent
    the dct data then this is the ticket. (as opposed to gmpy2.mpz objects).
    """
    dcts = orient_db.cur.execute("SELECT top_dct, bot_dct, id from orient").fetchall()
    ups = [np.uint64(up['top_dct']) for up in dcts]
    downs = [np.uint64(down['bot_dct']) for down in dcts]
    return ups, downs, [i['id'] for i in dcts]


def idname(id):
    r = peep.card_db.cur.execute("SELECT name, code, id from cards where id=?", (id,)).fetchone()
    return r['name'], r['code'], r['id']


def mean_dct(ups, downs):
    """
    this is not used in main(), just for investigating the self-similarity of entire groups of images.

    Parameters
    ----------
    ups: list of dct_hints of the upper part of a bunch of images
    downs: as above, but the lower part

    Returns
    -------
    tuple of three floats: mean of hamming distance of each up vs all other ups, ups vs each downs, downs vs downs
    """
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
    shows all the items that share each dct. a collision of sorts, from perfect similarity.
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
    """
    try to show pics given by a list of database ids
    """
    for i in ids:
        r = peep.card_db.cur.execute("SELECT pic_path, code, name from cards where id=?", (i,)).fetchone()
        if r:
            if r['pic_path']:
                cv2.imshow("{} {} {}".format(r['code'], r['name'], r['pic_path']),
                           cv2.imread(os.path.join(peep.__mtgpics__, r['pic_path'])))
            else:
                print("no pic: {} {}".format(r['name'], r['code']))
        else:
            print("{} is not an id code found in the database".format(i))
    return cv2.waitKey(wait)


def display(sameups, showall=False):
    """
    sameups: list of 3-tuples, [(nametext, cardset, database_id), ...]
    show groups of pics
    """
    for sames in sameups.viewvalues():
        # compare names against first entry, only show when differences
        if showall or any(s[0] != sames[0][0] for s in sames):
            ch = showpics([s[2] for s in sames])
            if ch == 27:
                cv2.destroyAllWindows()
                break
            else:
                cv2.destroyAllWindows()


def bring_up():
    """
    user sees card images with names containing user input string
    """
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


class Simile(object):
    def __init__(self, u, d, i):
        self.ups = np.vstack(np.array(u, dtype=object))
        self.dwn = np.vstack(np.array(d, dtype=object))
        self.ids = np.vstack(i)
        # vectorize lets gmpy2.hamdist get 'broadcast' over numpy arrays. speedily.
        self.gmp_hamm = np.vectorize(gmpy2.hamdist)

    def hamm_ups(self, dct, cutval):
        """
        dct: single mpz(uint64) to be compared against all the other values
        cutval: the hamming distance threshold to filter the list with

        Returns
        -------
        array of ids from the big list that have hamming distance less than cutval from 'dct'
        """
        return self.ids[np.where(self.gmp_hamm(self.ups,  dct) < cutval)]


def mirrorcards():
    cardlist = peep.card_db.cur.execute("SELECT id FROM cards").fetchall()
    dctstuff = [d['id'] for d in orient_db.cur.execute("SELECT id FROM orient").fetchall()]
    missing = [c['id'] for c in cardlist if not (c['id'] in dctstuff)]
    orient_db.cur.executemany("INSERT INTO orient (?)", missing)
    orient_db.con.commit()
    print("{} id are added to orient_db".format(len(missing)))
    if missing:
        print("{}".format(missing[0]))
    return 1


def init_and_check():
    """
    call this along with populate.py and picfinder.py to fill up database when running on remote server
    """
    mirrorcards()
    add_dct_data(cards())
    for nn, qq in find_faces(needed_faces(cards(), examine_zeros=False)).viewitems():
        print("with {} face(s) --> {}".format(nn, qq))


def main():
    """
    user can play with generated data & images on local machine.
    """
    init_and_check()
    a, b, c = getdcts()
    simulate = Simile(a, b, c)
    d, e, f = getdcts(only_faces=True)
    #todo: subclass Simile instead of re-running getdcts()
    smiles = Simile(d, e, f)
    default_distance = 15
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    print("- Press <c> to capture & compare & then to clear all cards - ")
    print("- Press <f> to only use cards with detected 'faces' in them -")

    while True:
        ret, frame = cap.read()
        FACE_ONLY = False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cv2.imshow('frame', gray)
        ch = cv2.waitKey(1) & 0xFF
        if ch == ord('f'):
            FACE_ONLY = True
            ch = ord('c')
        if ch == ord('c'):
            dct = dct_hint(gray)
            localface = face_cascade.detectMultiScale(cv2.equalizeHist(gray), scaleFactor=1.2, minNeighbors=3)
            # draw a captured image showing a box around detected faces
            if len(localface):
                img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                for (x, y, w, h) in localface:
                    cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.imshow("Faces", img)
            SEARCH = True
            ch = ''

            while SEARCH:
                if FACE_ONLY:
                    # pull from only the database items that have detected faces <f>
                    list1 = smiles.hamm_ups(dct, default_distance)
                    list2 = smiles.hamm_ups(dct, default_distance - 1)
                    print("faces only")
                else:
                    # pull from all database items <c>
                    list1 = simulate.hamm_ups(dct, default_distance)
                    list2 = simulate.hamm_ups(dct, default_distance - 1)
                    print("everything")
                if len(list1) < 1:
                    default_distance += 2
                    continue
                if len(list2) > 0:
                    default_distance -= 1
                    continue
                SEARCH = False
                print("at distance = {}".format(default_distance))
                ch = showpics(list1)

        if ch == 27:    # <esc>
            cv2.destroyAllWindows()
            print("quitting orientation")
            break
        if ch == ord('c'):
            cv2.destroyAllWindows()
        #display(find_sames(ups, ids), showall=False)
        #bring_up()

if __name__ == "__main__":
    exit(main())
