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
    args = parser.parse_args()

    verbose_level = 1
    if args.verbose:
        verbose_level = 2

    appstring = "OsmoBTS"
    appport = 4241
    vty = obscvty.VTYInteract(appstring, "127.0.0.1", appport)
    vty.command("enable")
    vty.command("bts 0 trx 0 ts 2 lchan 0 loopback")

