"""
gmp2 may need the gnu-mpc c library installed before it will work
grequests needs greenlet, which needs a c compiler to install itself
cv2 is opencv - 2.4.x or 3.x - cv2.so or cv2.pyd should be placed in the 'site-packages' your python interp. is using
numpy and python-Levenshtein are also in need of a compiler for their self-install

Marlin, with my own "Configuration.h" is used for the firmware uploaded to RAMPS 1.4 style hardware for robot control
"""

from distutils.core import setup

setup(
        name='CardSnake',
        version='.1',
        packages=['requests', 'grequests', 'python-Levenshtein', 'gmpy2', 'numpy', 'path.py', 'cv2'],
        url='https://github.com/Joesuber/CardSnake',
        license='MIT',
        author='Joe Suber',
        author_email='joesuber@gmail.com',
        description='scrape together data & images of Magic: the Gathering cards. Serve them up by similarity measures.'
)
