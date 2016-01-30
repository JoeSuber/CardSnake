# CardSnake
This will scrape and download to create a local database and file-tree of card images.
Then it will let you play with things. The tools will evolve.

To run this you will need python2.7.xx:

https://www.python.org/downloads/

Also, opencv. Get a binary installer for your platform from:

https://opencv.org

Find the 'cv2.so' (linux, OSX) or 'cv2.pyd' (windows) file.

It is  in your opencv install directory, e.g.

> ../opencv/build/python/2.7/x86  (32-bit, for most windows installs)

or

> ../opencv/build/python/2.7/x64    (64-bit)

copy the cv2.* file you find there to your python install dir:

> ../Python27/Lib/site-packages

You may need to get a few other python packages.

From the command line, (on windows use: winkey-x [command prompt (admin)])

>pip install requests grequests python-Levenshtein gmpy2 numpy

(installer stuff happens)

Now for the fun part!

get your command line to where you copied/cloned all the CardSnake files and type:

>> python populate.py

(stuff happens)

>> python picfinder.py

(stuff happens for a few minutes)

>> python orientation.py

(on the first run, it may take a while to calculate and store all the DCT data, maybe 20 minutes)
(a camera view pops up. press 'c' or 'f') 

Make funny faces into your web cam, or show it the art on a card. It will show you what is most similar.

Update / check for new data by re-running the above stuff in order. 
It only updates what needs updating so it will be much faster.

Have fun!