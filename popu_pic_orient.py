"""
runs the modules from the project required to set up the database, download image files,
pre-process the images to obtain some similarity measures, and check to see if new info
or images exist to be had from sources, getting them into the local fold as well.
"""

import populate
import picfinder
import orientation
import pricer

populate.main()
picfinder.main()
orientation.init_and_check()
pricer.main()

print("creation, updates, orientation and pricing are finished")
