#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

--- Python driven Alarm Clock ---

Lichtwecker Project from Griesi for my beloved cousins C and S


"""
from transitions import Machine

import RPi.GPIO as GPIO
import sys
import time
from easysettings import EasySettings

# mpd lib
from mpd import MPDClient

# own helpers
import helpers

#sys.path.append(r'/home/pi/pysrc')
#import pydevd
#pydevd.settrace('192.168.178.138') # replace IP with address 
                                # of Eclipse host machine


# Main function
def main(argv):

    lichtwecker = helpers.LichtWecker()
    lichtwecker.start()
    print ("Lichtwecker object created and started")
    while 1:
        time.sleep(1)

if __name__ == "__main__":
#    pass
    main(sys.argv)