#!/usr/bin/env python
import re
import sys
import argparse

CONFIG_FILE_NAME = '/etc/sv/osmo-trx/run'
OPTION = '-S'

parser = argparse.ArgumentParser()
parser.add_argument("trx", type=str, default='',
                    help="Pass 'TRX1' to choose TRX1 as primary TRX. "
                         "Pass 'TRX2' to choose TRX2 as primary TRX. "
                         "Omit to read the current setting.")
args = parser.parse_args()

action = args.trx

#
# Read file
#

f = open(CONFIG_FILE_NAME, 'r')
lines = f.readlines()
f.close()

#
# Process the file
#

trx_re = re.compile(r'^[^#].* osmo-trx ')
for i in range(len(lines)):
    if trx_re.match(lines[i]) is not None:
        s = lines[i].split()
        if action == 'TRX1':
            # Remove '-S'
            if OPTION in s:
                s.remove(OPTION)
                lines[i] = ' '.join(s) + '\n'
            print "TRX1"
        elif action == 'TRX2':
            # Add '-S'
            if OPTION not in s:
                s.append(OPTION)
                lines[i] = ' '.join(s) + '\n'
            print "TRX2"
        elif action == '':
            # Check '-S'
            if OPTION in s:
                print "TRX2"
            else:
                print "TRX1"
            sys.exit()
        else:
            raise RuntimeError('Unkown action selected')

#
# Write the file back
#

f = open(CONFIG_FILE_NAME, 'w')
f.writelines(lines)
f.close()
