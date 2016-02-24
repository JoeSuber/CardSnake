# CardSnake
This will scrape and download to create a local database and file-tree of card images.
Then it will let you play with things. These tools will evolve.

To run this you will need python2.7.xx:

https://www.python.org/downloads/

Also, opencv. Get a binary installer for your platform from:

https://opencv.org

Find the 'cv2.so' (linux, OSX) or 'cv2.pyd' (windows) file.

It is in your opencv install directory, e.g.

> ../opencv/build/python/2.7/x86  (32-bit, for most windows installs)

or

> ../opencv/build/python/2.7/x64    (64-bit)

copy the cv2.* file you find there to your python install dir:

> ../Python27/Lib/site-packages

You may need to get a few other python packages.

From the command line, (on windows use: winkey-x [command prompt (admin)])

>pip install requests grequests python-Levenshtein gmpy2 numpy path.py

(installer stuff happens)

Now for the fun part!

get your command line to where you copied/cloned all the CardSnake files and type:

>> python popu_pic_orient.py

(stuff happens, data is acquired, pics downloaded & processed for maybe 30 minutes)

next, type:

>> python educator.py

A camera view pops up. get out your Magic cards. Make sure the window is 'up front' in your gui

press 'k' [k]ompare or 'c' to [c]lear or 'Esc' (to quit)

>> python orientation.py

Make funny faces into your web cam, press 'c' or 'f' What is most similar?

Update / check for new data, new card-sets by re-running 'popu_pic_orient.py'.
It only updates what needs updating so it will be much faster now.

Notice that you now have a local /CardSnake/pics/ sub-directory full of all the up to date card images (.jpg format). 
29,500+ of them as of this date.

Have fun!