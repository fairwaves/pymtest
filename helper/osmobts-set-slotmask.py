#!/usr/bin/env python
import obscvty

if __name__ == '__main__':
    import argparse
    import os
    import sys
    import re

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose",
                        action="store_true", help="verbose mode")
    for i in range(8):
        parser.add_argument("ts%d"%i, type=int, choices = range(0, 2), metavar = 'TS%d'%i, help="Enable timeslot %d? [0..1]"%i)
    args = parser.parse_args()

    verbose_level = 1
    if args.verbose:
        verbose_level = 2

    appstring = "OsmoBTS"
    appport = 4241
    vty = obscvty.VTYInteract(appstring, "127.0.0.1", appport)
    vty.command("enable")
    vty.command("configure terminal")
    vty.command("bts 0")
    vty.command("trx 0")
    vty.command("slotmask %d %d %d %d %d %d %d %d" % (args.ts0, args.ts1, args.ts2, args.ts3, args.ts4, args.ts5, args.ts6, args.ts7))

