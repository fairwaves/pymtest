#!/usr/bin/env python
# -*- coding: utf-8 -*-

from umtrx_property_tree import umtrx_property_tree
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("dcdc_val", type=int, choices=range(0, 256),
                    metavar='dcdc_val', help="DCDC control value [0..255]")
args = parser.parse_args()

s = umtrx_property_tree()
s.connect()

path = "/mboards/0/pa_dcdc_r"
s.set_int(path, args.dcdc_val)

s.close()
