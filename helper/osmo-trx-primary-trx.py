#!/usr/bin/env python
import re
import sys
import argparse

CONFIG_FILE_NAME = '/etc/sv/osmo-trx/run'
OPTION = '-S'

parser = argparse.ArgumentParser()
parser.add_argument("trx", type=str, default='',
                    help="Pass '1' to choose TRX1 as the primary TRX. "
                         "Pass '2' to choose TRX2 as the primary TRX. "
                         "Pass '?' to read the current setting.")
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

trx_re = re.compile(r'^[^#].*[/ ]osmo-trx ')
for i in range(len(lines)):
    if trx_re.match(lines[i]) is not None:
        s = lines[i].split()
        if action == '1':
            # Remove '-S'
            if OPTION in s:
                s.remove(OPTION)
                lines[i] = ' '.join(s) + '\n'
            print "1"
        elif action == '2':
            # Add '-S'
            if OPTION not in s:
                s.append(OPTION)
                lines[i] = ' '.join(s) + '\n'
            print "2"
        elif action == '?':
            # Check '-S'
            if OPTION in s:
                print "2"
            else:
                print "1"
            sys.exit()
        else:
            raise RuntimeError('Unkown action selected')

#
# Write the file back
#

if action == '?':
    # Normally we shouldn't get here
    print "unknown"
else:
    f = open(CONFIG_FILE_NAME, 'w')
    f.writelines(lines)
    f.close()
