#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

--- Python driven Alarm Clock ---

Lichtwecker Project from Griesi for my beloved cousins C and S

"""
import sys
import time
import helpers # own helpers
import locale

# sys.path.append(r'/home/pi/pysrc')
# import pydevd
# pydevd.settrace('192.168.178.23') # replace IP with address 
                                # of Eclipse host machine




# Main function
def main(argv):

    locale.setlocale(locale.LC_ALL, 'de_DE') # for German weekday names

    lichtwecker = helpers.LichtWecker()
    lichtwecker.start()
    print ("Lichtwecker object created and started")
    while 1:
        time.sleep(1)

if __name__ == "__main__":
#    pass
    main(sys.argv)