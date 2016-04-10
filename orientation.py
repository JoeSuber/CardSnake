#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
generate some dct data if needed. Use it to help determine the most similar images to a captured image.

run populate first, then picfinder, then run orientation and wait a few minutes while new dcts are added to database
"""
from collections import defaultdict, Counter
from operator import itemgetter
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


@contextmanager
def Mytime(scoresheet):
    start = clock()
    try:
        yield
    finally:
        scoresheet.append(clock()-start)


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
    print("Calculating DCT data for {} items...".format(len(cardpaths)))
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
            try:
                flim = im[::-1, ::-1]
                height, width = im.shape[:2]
                datas.append({'id': idc, 'picpath': shortpath,
                          'top_dct': gmpy2.digits(dct_hint(im[:width * __RAT__, :])),
                          'bot_dct': gmpy2.digits(dct_hint(flim[:width * __RAT__, :]))})
            except TypeError as e:
                print("{} No picture was loaded for path: {}".format(e, fsp))
    print("{} new pics dct'd".format(counter))
    print("adding {} new lines of data to orient from {} card-paths".format(len(datas), len(cardpaths)))
    if datas:
        orient_db.add_data(datas, 'orient', 'id')
        print("committed!")

    q = orient_db.cur.execute("SELECT id FROM orient").fetchall()
    print("there are now {} lines in orient".format(len(q)))
    return datas


def idname(id):
    r = peep.card_db.cur.execute("SELECT name, code, id from cards where id=?", (id,)).fetchone()
    return r['name'], r['code'], r['id']


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
        self.default_distance = 6
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

    def handful(self, img, flipit=15, dist=None):
        """
        img: full image probably lifted from a user input device
        flipit: the hamming distance where it may be wise to try an inverted version of img to get closer results

        Returns
        -------
        list1: a list of 4 or more ids-to-database-images with the closest hamming distance
        to the top of the input img dct.
        """
        if dist is None:
            dist = self.default_distance
        dct = dct_hint(cv2.equalizeHist(cv2.cvtColor(img[:img.shape[1] * __RAT__, :], cv2.COLOR_BGR2GRAY)))
        SEARCH = True
        while SEARCH:
            list1 = self.hamm_ups(dct, dist)
            if len(list1) < 4:
                dist += 2
                continue
            if len(self.hamm_ups(dct, dist - 1)) > 3:
                dist -= 1
                continue
            SEARCH = False
        #print("results at distance: {} (flipit={})".format(self.default_distance, flipit))
        if dist > flipit:
            return self.handful(img[::-1, ::-1], flipit=flipit+1, dist=dist-5)
        #print("".join(("{:3}: {}{}".format(n+1, idname(l)[:2], os.linesep) for n, l in enumerate(list1))))
        return list1

    def updown(self, img, rng=(4, 18)):
        """ for testing different efficient ways of telling up from downc """
        dct = dct_hint(cv2.equalizeHist(cv2.cvtColor(img[:img.shape[1] * __RAT__, :], cv2.COLOR_BGR2GRAY)))
        dd = {}
        for dist in xrange(rng[0], rng[1]):
            dd[dist] = (len(self.hamm_ups(dct, dist)), len(self.hamm_down(dct, dist)))
        return dd

    def fistfull(self, img, trips=0, grip=1):
        """ replaces handful with a rube-goldberg machine """
        if trips > 2:
            # always gives at least one result but always uses the same quantity of costly operations
            dcts = [dct_hint(cv2.equalizeHist(cv2.cvtColor(im[:int(im.shape[1] * __RAT__), :], cv2.COLOR_BGR2GRAY)))
                    for im in [img, img[::-1, ::-1]]]
            start, uplist = 5, {}
            # counting the zeroes determines the quality of each list (fewer=better) and
            # index of first result > 0 (plus starting value) is the min cut value for generating the list of ids
            for tag, dct in enumerate(dcts):
                uplist[tag] = [np.sum(self.gmp_hamm(self.ups, dct) < dist) for dist in xrange(start, 19)].count(0)
            best_idx, first_result = sorted([(k, v) for k, v in uplist.viewitems()], key=itemgetter(1))[0]
            print("*** used long way home ***")
            return self.hamm_ups(dcts[best_idx], first_result + start + grip)  # success!

        # uses pre-calculated "downs" to avoid doing two dcts on sample, and can exit early very often
        # also tries to return more than 1 result in an effort to give the matcher some options
        dct = dct_hint(cv2.equalizeHist(cv2.cvtColor(img[:int(img.shape[1] * __RAT__), :], cv2.COLOR_BGR2GRAY)))
        for dist in xrange(6, 20):
            ups = np.sum(self.gmp_hamm(self.ups,  dct) < dist)
            downs = np.sum(self.gmp_hamm(self.dwn,  dct) < dist)
            # print("{:3}:  ups {},  downs {}".format(dist, ups, downs))
            if ups == downs:
                continue
            if (ups > (3 - trips)) and (ups > (downs - trips)):
                return self.hamm_ups(dct, dist)     # success!
            if (downs > trips) and (downs > ups):
                return self.fistfull(img[::-1, ::-1], trips=trips+1)     # recur a little bit

        print("Simile.fistfull() can't make head nor tail of the image!")
        return []


def mirror_cards():
    """
    see which items in card db need to be added to orient, then add them.
    """
    orient_db.cur.execute("""INSERT or IGNORE INTO orient(id, picpath)
                              SELECT id, pic_path FROM cards WHERE pic_path IS NOT NULL""")
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


def get_kpdesc(id, c1='ak_points', c2='ak_desc'):
    """
    retrieve and re-hydrate the key-point and descriptor data for a single card id
    """
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
        # remove missing paths
    cardstack = {}
    for want in needed:
        full_path = os.path.join(fs, want['picpath'])
        if os.path.isfile(full_path):
            cardstack[want['id']] = full_path
    if not cardstack:
        print("finished adding keypoint and descriptor data")
        return 0
    with Timer(msg="processing {} new items".format(len(cardstack))):
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
