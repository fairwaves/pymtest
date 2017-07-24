#!/usr/bin/env python
import sys
from gps import *
from datetime import datetime

try:
    session = gps()
    session.stream(WATCH_ENABLE)

    for report in session:
        if report['class'] == 'TPV' and report['tag'] == 'GLL':
            time = datetime.strptime(report['time'], "%Y-%m-%dT%H:%M:%S.000Z")
            today = datetime.today()

            delta = (time - today).total_seconds()
            print ("%s %+f" % (today, delta))

            if abs(delta) < 45:
                print("SUCCESS")
                sys.exit(0)
            else:
                print("Detected system time lag: %f seconds" % delta)
                sys.exit(4)

except IOError as e:
    print("ERROR: " + str(e))

sys.exit(2)
