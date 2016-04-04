#!/usr/bin/env python -S
# -*- coding: utf-8 -*-

"""
functions and things removed from the modules that are actually being used.
Though this is done in pursuit of clarity:
"Those that don't study history..."
"""



def dct_hint2(im, hsize=32):
    """ doesn't give the same results due to some undercover type coercion, and is a hair slower"""
    q = mpz()
    bumpy = cv2.dct(np.array(cv2.resize(im, dsize=(hsize, hsize),
                                        interpolation=cv2.INTER_AREA), dtype=np.float32))[:8, 1:9]
    #print(bumpy.ravel() > np.mean(bumpy))
    for i in np.where(np.hstack(bumpy > np.mean(bumpy)))[0]:
        q += 1 << i
    return q


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
