#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
generate some dct data if needed. Use it to help determine the most similar images to a captured image.

run populate first, then picfinder, then run orientation and wait a few minutes while new dcts are added to database
"""
from collections import defaultdict, Counter, deque
import gmpy2
from gmpy2 import mpz
from cv2_common import *
from sqlite3 import Binary
import populate as peep
import sys
reload(sys).setdefaultencoding("utf8")
# import cv2
# import numpy as np
# import json
# import os

__RAT__ = 0.80  # image height = __RAT__* width. This mostly puts top-image's-bottom-border at art-line

#peep.card_db.cur.execute("DROP TABLE orient")

orient_db = peep.DBMagic(DBfn=peep.__sqlcards__,
                         DBcolumns={'orient': peep.createstr.format('orient', peep.__cards_key__)},
                         DB_DEBUG=True)

orient_db.add_columns('orient', {'top_dct': 'TEXT', 'bot_dct': 'TEXT', 'picpath': 'TEXT', 'face': 'INTEGER'})


def dct_hint(im, hsize=32):
    """ returning DCT hash as 64-bit mpz int, which makes popcount faster"""
    q = mpz()
    bumpy = cv2.dct(np.array(cv2.resize(im, dsize=(hsize, hsize),
                                        interpolation=cv2.INTER_AREA), dtype=np.float32))[:8, 1:9]
    #print((bumpy>np.mean(bumpy)).ravel())
    for i, j in enumerate((bumpy > np.mean(bumpy)).ravel()):
        if j:
            q += 1 << i
    return q


def dct_hint2(im, hsize=32):
    """ doesn't give the same results due to some undercover type coercion, and is a hair slower"""
    q = mpz()
    bumpy = cv2.dct(np.array(cv2.resize(im, dsize=(hsize, hsize),
                                        interpolation=cv2.INTER_AREA), dtype=np.float32))[:8, 1:9]
    #print(bumpy.ravel() > np.mean(bumpy))
    for i in np.where(np.hstack(bumpy > np.mean(bumpy)))[0]:
        q += 1 << i
    return q


@contextmanager
def Mytime(scoresheet):
    start = clock()
    try:
        yield
    finally:
        scoresheet.append(clock()-start)


def race(picquant=100, pics='pics/2ED/un{}.jpg', alg1=dct_hint2, alg2=dct_hint):
    """
    for testing speed of some similar functions
    """
    pics = [cv2.equalizeHist(cv2.imread(pics.format(x), cv2.IMREAD_GRAYSCALE)) for x in xrange(1, picquant+1)]
    print("{} pics loaded".format(len(pics)))
    time1, time2, res1, res2 = [], [], [], []
    sched = [np.random.rand() > 0.5 for x in xrange(len(pics))]
    order=[(alg1, time1, res1), (alg2, time2, res2)]
    for n, s in enumerate(sched):
        pic = pics[n]
        if s:
            order = [order[1], order[0]]
        for alg, t, results in order:
            with Mytime(t):
                results.append(alg(pic))

    for al, t, __ in order:
        v = np.vstack(t)
        w, s = np.mean(v)*1000, np.std(v)*1000
        print("{}: {} trials, mean time: {}ms, stdev: {}ms".format(al.__repr__(), len(t), w, s))

    for n, (a, b) in enumerate(zip(order[0][2], order[1][2])):
        try:
            assert(a==b)
        except Exception:
            print("{:6}: {:0b} of {} not equal to {:0b} of {}".format(n, a, type(a), b, type(b)))


def cards(fs=peep.__mtgpics__):
    # joins unique part of path to local path-stub or sends a None if path is None.
    cardmap = {}
    for line in orient_db.cur.execute("SELECT id, picpath from orient").fetchall():
        #print("fs={}   picpath={}".format(fs, line['pic_path']))
        if line['picpath']:
            cardmap[line['id']] = os.path.join(fs, line['picpath'])
    return cardmap


def needed_faces(cardmap, examine_zeros=False):
    """
    filter cardmap to include only items that need examination for faces.
    defaults to only examining 'null' valued, new items, not zeroes.
    """
    needed = {}
    for id, cardpath in cardmap.viewitems():
        if os.path.isfile(cardpath):
            card_has_face = orient_db.cur.execute("SELECT face FROM orient WHERE id=?", (id,)).fetchone()[0]
            if card_has_face is None or (examine_zeros and not card_has_face):
                needed[id] = cardmap[id]
    return needed


def find_faces(cardmap, scale=1.25, min_neighbor=4):
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
        print("All face detection was done previously")
        return facecount
    print("face finder will examine {} pictures, using scale={} minNeighbors={}"
          .format(len(cardmap), scale, min_neighbor))
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    for n, (id, cardpath) in enumerate(cardmap.viewitems()):
        faces = face_cascade.detectMultiScale(cv2.equalizeHist(cv2.imread(cardpath, cv2.IMREAD_GRAYSCALE)),
                                              scaleFactor=scale, minNeighbors=min_neighbor)
        face_quant = len(faces)
        if face_quant:
            print("{}: {}: has {} face{}".format(n, cardpath, face_quant, 's' if face_quant > 1 else ''))
        facecount[face_quant] += 1
        orient_db.cur.execute("UPDATE orient SET face=(?) WHERE id=(?)", (face_quant, id))
    orient_db.con.commit()
    return facecount


def add_dct_data(cardpaths):
    """
    sock away top and bottom dcts of pics as a persistent 64-bit int
    cardpaths = {card['id']: os.path.join(__local_dir__, card['pic_path']), card['id']: None, ...}
    cardpaths should be drawn from card_db where they are already vetted
    """
    datas = []
    counter = 0
    print("Calculating DCT data...")
    for idc, fsp in cardpaths.viewitems():
        #id, top_dct, picpath, face
        current_card = orient_db.cur.execute("SELECT id, top_dct FROM orient WHERE id=(?)", (idc,)).fetchone()
        #print "AFF", fsp, current_card
        if fsp and not current_card['top_dct']:
            counter += 1
            if not (counter % 200):
                print("{} new pics dct'd".format(counter))
            shortpath = os.path.sep.join(fsp.split(os.path.sep)[-2:])
            im = cv2.equalizeHist(cv2.imread(fsp, cv2.IMREAD_GRAYSCALE))
            height, width = im.shape[:2]
            datas.append({'id': idc, 'picpath': shortpath,
                          'top_dct': gmpy2.digits(dct_hint(im[:width*__RAT__, :width])),
                          'bot_dct': gmpy2.digits(dct_hint(im[height - width*__RAT__:height, :width]))})
    print("{} new pics dct'd".format(counter))
    print("adding {} new lines of data to orient from {} card-paths".format(len(datas), len(cardpaths)))
    if datas:
        orient_db.add_data(datas, 'orient', 'id')
        print("committed!")

    q = orient_db.cur.execute("SELECT id FROM orient").fetchall()
    print("there are now {} lines in orient".format(len(q)))
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
    def __init__(self, just_faces=False):
        outgoing = np.vstack(((mpz(line['top_dct']), mpz(line['bot_dct']), line['face'], line['id']) for line in
                              orient_db.cur.execute("SELECT top_dct, bot_dct, id, face FROM orient").fetchall()))
        facemask = np.where(outgoing[:, 2] >= just_faces)
        self.ups = outgoing[facemask, 0]
        self.dwn = outgoing[facemask, 1]
        self.ids = outgoing[facemask, 3]
        self.default_distance = 15
        # vectorize lets gmpy2.hamdist get 'broadcast' over numpy arrays. speedily.
        self.gmp_hamm = np.vectorize(gmpy2.hamdist)

    def hamm_ups(self, dct, cutval):
        """
        dct: single mpz(uint64) to 'hamm' against all the other values
        cutval: the hamming distance threshold with which to filter the array

        Returns
        -------
        array of ids from the big list that have hamming distance less than cutval from 'dct'
        """
        return self.ids[np.where(self.gmp_hamm(self.ups,  dct) < cutval)]

    def hamm_down(self, dct, cutval):
        return self.ids[np.where(self.gmp_hamm(self.dwn,  dct) < cutval)]

    def is_top(self, dct):
        print "score ups:  ", np.sum(self.gmp_hamm(self.ups, dct))
        print "score down: ", np.sum(self.gmp_hamm(self.dwn, dct))
        return np.sum(self.gmp_hamm(self.ups, dct)) < np.sum(self.gmp_hamm(self.dwn, dct))

    def handful(self, img, flipit=15):
        """
        img: full image probably lifted from a user input device
        flipit: the hamming distance where it may be wise to try an inverted version of img to get closer results

        Returns
        -------
        list1: a minimal list of ids-to-database-images with the closest hamming distance
        to the top or bottom of the input img dct.
        """
        d = dct_hint(cv2.equalizeHist(cv2.cvtColor(img[0:img.shape[1] * __RAT__, :], cv2.COLOR_BGR2GRAY)))
        SEARCH = True
        while SEARCH:
            list1 = self.hamm_ups(d, self.default_distance)
            list2 = self.hamm_ups(d, self.default_distance - 1)
            if len(list1) < 3:
                self.default_distance += 2
                continue
            if len(list2) > 2:
                self.default_distance -= 1
                continue
            SEARCH = False
        #print("results at distance: {} (flipit={})".format(self.default_distance, flipit))

        if self.default_distance > flipit:
            return self.handful(img[::-1, ::-1], flipit=flipit+1)

        #print("".join(("{:3}: {}{}".format(n+1, idname(l)[:2], os.linesep) for n, l in enumerate(list1))))
        return list1


def mirror_cards():
    """
    see which items in card db need to be added to orient, then add them.
    """
    orient_db.cur.execute("""INSERT or IGNORE INTO orient(id, picpath)
                              SELECT id, pic_path from cards WHERE pic_path IS NOT NULL""")
    orient_db.con.commit()
    return 1


def akazer(pics=None, akaze=None, columns='ak_points,ak_desc'):
    """
    Not just for AKAZE any more!

    Parameters
    ----------
    pics = {id: local-path-to-pic, ...}
    akaze = cv2.AKAZE_create() or cv2.ORB_create() or cv2.KAZE_create() etc..
    columns = two comma separated column names for the new data
    Returns
    -------
    list of image data formatted for entering into cards database
    """
    new_data = []
    if pics is None:
        pics = cards()
    if akaze is None:
        akaze = cv2.AKAZE_create()
    c1, c2 = columns.split(',')
    for kk, vv in pics.viewitems():
        if vv:
            im = cv2.imread(vv)
        else:
            im = None
        if im is not None:
            akps, adesc = akaze.detectAndCompute(im, None)
            jk = [(a.pt, a.angle, a.class_id, a.octave, a.response, a.size) for a in akps]
            new_data.append({'id': kk, c1: jk, c2: Binary(adesc.dumps())})
        else:
            print("for id: {}, akazer failed to find pic on path: {}".format(kk, vv))
    return new_data


def get_kpdesc(id, columns='ak_points,ak_desc'):
    """
    retrieve and re-hydrate the key-point and descriptor data for a single card id
    """
    c1, c2 = columns.split(',')
    try:
        line = orient_db.cur.execute("SELECT {}, {} FROM orient WHERE id=?".format(c1, c2), (id,)).fetchone()
        assert(line[c1] is not None)
        assert(line[c2] is not None)
    except Exception as e:
        print("{} -- trouble fetching kp from orient: {} for {}, {}".format(e, id, c1, c2))
        return [], None
    return [cv2.KeyPoint(x=a[0][0], y=a[0][1], _angle=a[1], _class_id=a[2], _octave=a[3], _response=a[4], _size=a[5])
            for a in line[c1]], np.loads(str(line[c2]))


def run_akazer(workchunk=100, db=orient_db, dbtable='orient', columns='ak_points,ak_desc', fs=peep.__mtgpics__):
    pntcol, desc_col = columns.split(',')
    ADD_COLUMNS = False
    current_columns = db.show_columns(dbtable)
    if (pntcol not in current_columns) or (desc_col not in current_columns):
        ADD_COLUMNS = True
        needed = db.cur.execute("SELECT id, picpath FROM {} WHERE picpath IS NOT NULL"
                                .format(dbtable)).fetchmany(size=workchunk)
    else:
        needed = db.cur.execute("SELECT id, picpath FROM {} WHERE picpath IS NOT NULL and {} IS NULL"
                                .format(dbtable, pntcol)).fetchmany(size=workchunk)
    if len(needed) < 1:
        print("finished adding keypoint and descriptor data")
        return 0
    cardstack = {want['id']: os.path.join(fs, want['picpath']) for want in needed}
    with Timer(msg="processing {} new items".format(workchunk)):
        dataa = akazer(pics=cardstack, columns=columns)
        if ADD_COLUMNS:
            db.add_columns(dbtable, peep.column_type_parser(dataa))
        db.add_data(dataa, dbtable, key_column='id')
    return 1


def init_and_check():
    """
    call this along with populate.py and picfinder.py to fill up database when running on remote server
    """
    mirror_cards()
    #print("mirror done")
    add_dct_data(cards())
    #print("add dct done")
    for nn, qq in find_faces(needed_faces(cards(), examine_zeros=False)).viewitems():
        print("with {} face(s) --> {}".format(nn, qq))
    while run_akazer(workchunk=150, db=orient_db, dbtable='orient', columns='ak_points,ak_desc'):
        continue


"SELECT id, picpath FROM {} WHERE picpath IS NOT NULL and {} IS NULL"
FLANN_INDEX_KDTREE = 1
FLANN_INDEX_LSH = 6
flann_pms = dict(algorithm=FLANN_INDEX_LSH,
                 table_number=6,            # 12
                 key_size=12,               # 20
                 multi_probe_level=1)       # 2


def main():
    """
    user can play with generated data & images on local machine.
    This is mostly obsolete. Try running 'educator.py'
    """
    init_and_check()
    simulate = Simile(just_faces=False)
    smiles = Simile(just_faces=True)
    default_distance = 15
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    print("- Press <c> to capture & compare & then to clear all cards - ")
    print("- Press <f> to only use cards with detected 'faces' in them -")
    kazy = cv2.AKAZE_create()
    flann_params = flann_pms
    flann = cv2.FlannBasedMatcher(flann_params, {})
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
            cv2.destroyAllWindows()
            localface = face_cascade.detectMultiScale(cv2.equalizeHist(gray), scaleFactor=1.2, minNeighbors=3)

            if len(localface) and FACE_ONLY:
                xf, yf, wf, hf = 0, 0, 0, 0
                for (x, y, w, h) in localface:
                    xf, yf = max(xf, x-20), max(yf, y-30)
                    wf, hf = min(xf + w + 40, gray.shape[1]), min(yf + h + 60, gray.shape[0])
                img = gray[yf:hf, xf:wf]
                kp, desc = kazy.detectAndCompute(img, None)
                cv2.imshow("Face only", img)
                dct = dct_hint(img)
                img1 = img
            else:
                cv2.imshow("frame", gray)
                kp, desc = kazy.detectAndCompute(gray, None)
                dct = dct_hint(gray)
                img1 = gray
            SEARCH = True
            ch = ''

            while SEARCH:
                if FACE_ONLY:
                    # pull from only the database items that have detected faces <f>
                    list1 = smiles.hamm_ups(dct, default_distance)
                    list2 = smiles.hamm_ups(dct, default_distance - 1)
                    FACE_ONLY = False
                else:
                    # pull from all database items <c>
                    list1 = simulate.hamm_ups(dct, default_distance)
                    list2 = simulate.hamm_ups(dct, default_distance - 1)
                if len(list1) < 2:
                    default_distance += 2
                    continue
                if len(list2) > 1:
                    default_distance -= 1
                    continue

                SEARCH = False

                print("at distance = {}".format(default_distance))
                for num, l in enumerate(list1):
                    ckp, cdesc = get_kpdesc(l)
                    allmn = flann.knnMatch(desc, cdesc, k=2)
                    filtered_m = []
                    if len(allmn) > 1:
                        try:
                            filtered_m = [[m] for m, n in allmn if m.distance < (0.75 * n.distance)]
                        except ValueError:
                            print("error unpacking...probably missing a paired DMatch object")
                            filtered_m = []
                    if filtered_m:
                        imp = orient_db.cur.execute("SELECT picpath FROM orient WHERE id=(?)", (l,)).fetchone()
                        img2 = cv2.imread(os.path.join(peep.__mtgpics__, imp['picpath']))
                        img3 = cv2.drawMatchesKnn(img1, kp, img2, ckp, filtered_m,
                                                  outImg=np.zeros((600, 800), dtype=np.uint8), flags=2)
                        cv2.imshow("{}".format(num), img3)
                    # print len(matches), matches[0][0].distance, matches[0][1].distance
                ch = cv2.waitKey(0) & 0xFF

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
