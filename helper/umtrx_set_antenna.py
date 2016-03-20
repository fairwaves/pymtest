#!/usr/bin/env python
# -*- coding: utf-8 -*-

from umtrx_property_tree import umtrx_property_tree
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("rx_antenna", type=str,
                    metavar='rx_antenna', help="Select antenna for Rx")
parser.add_argument("tx_antenna", type=str,
                    metavar='tx_antenna', help="Select antenna for Tx")
args = parser.parse_args()

s = umtrx_property_tree()
s.connect()

for side in ["A", "B"]:
    path = "/mboards/0/dboards/"+side+"/rx_frontends/0/antenna/value"
    print s.set_string(path, args.rx_antenna)
    path = "/mboards/0/dboards/"+side+"/tx_frontends/0/antenna/value"
    print s.set_string(path, args.tx_antenna)

s.close()
