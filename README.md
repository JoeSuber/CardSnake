# CardSnake
This will scrape and download to create a local database and file-tree of card images.
Then it will let you play with things. The tools will evolve.

To run this you will need python2.7.xx:

https://www.python.org/downloads/

Also, opencv. Get a binary installer for your platform from:

https://opencv.org

for opencv, find the cv2.so (linux, OSX) or cv2.pyd (windows) file.
It is in your opencv install directory, e.g.

/opencv/build/python/2.7/x86  (32-bit, for most windows installs)
or
/opencv/build/python/2.7/x64    (64-bit)

copy the cv2.* file you find to your python install:

Python27/Lib/site-packages  (directory of your python install)
sometimes this is all taken care of by the installer, but ymmv.

Then you may need to get a few python packages.
From the command line, (on windows use: winkey-<x> [command prompt (admin)])

pip install requests grequests python-Levenshtein gmpy2 numpy

now get your command line to where you copied/cloned all the CardSnake files and type:

python populate.py

python picfinder.py

python orientation.py

Make funny faces into your web cam, or show it the art on a card. Have fun!