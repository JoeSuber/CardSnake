"""
use orient db to:
1) allow user to take a pic via camera, save it to a local dir, get dct and keypoint/desc info into db
    a) must create 'id' hash, and a meaningful filename, ensuring no collisions on 'id'.
    b) for these non-stock images, choose and record some 'best matches'
       (list of ids) from among the stock images
    c) maybe allow user intervention via text entry or gui image selection
    d) for repeated similar user-images, test to see if hamming distances to pre-computed items are always
        significantly lower than against the stock images
    e) build this with inclusion into the robot control loop in mind

2) test flann matcher capability to handle multiple sets of objects. Find the trade-offs that are acceptable between
    the quantity of keypoints-per-object (ie probably between 30 - 600) and speed/capacity/accuracy of matcher.
    Allow for testing different flann-parameters or even getting the auto-tune thing working.
    a) key-points could be winnowed by strength or re-computed to a given max/min quantity per pic.
    b) test: perhaps don't use the matcher's '.add()' internals - just search entire db for a threshold of 'hits'
        this could terminate the search early, and then optimize by prioritizing subsequent searches on the
        (pre-loaded?) ids that share set-codes with recently found items. Thus we can often narrow the brute-force
        problem by a couple orders of magnitude since most physical stacks of cards will be randomly drawn from only a
        few of the possible sets. Maybe introduce some 'softer' bias in favor of recent sets.

3) in service to both above items, fix-up a bounding box, and a 'shutter-open-close' widget for the camera.
    include rotations / flips to help in determining the orientation / affine transform (if needed) to find proper
    sample from the image. Homography from key-points could be found and coded in to capture to allow convenient
    physical camera offset.
    Find out what the standard deviations, means and medians are for hamming distances when the subject is oriented
    'right-side-up' vs 'upside-down' Build some efficient logic for orientation::Simile that tells this vital bit of
    info given dct_hints..
        a) Build some multiple-sample based recognition into database for the card back (based on input images).
            Perhaps some 'hard-coded' dct_hint could be included in source-code for card backs
"""

