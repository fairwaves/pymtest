#!/usr/bin/env python
import sys
from gps import *
from datetime import tzinfo, timedelta, datetime
import dateutil.parser

ZERO = timedelta(0)

class UTC(tzinfo):
  def utcoffset(self, dt):
    return ZERO
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return ZERO


try:
    session = gps()
    session.stream(WATCH_ENABLE)

    for report in session:
#        print(str(report))
        if report['class'] == 'TPV' and (report['tag'] == 'GLL' or report['tag'] == 'RMC'):
            time = dateutil.parser.parse(report['time'])
            today = datetime.now(UTC())

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

print("ERROR: Empty session")
sys.exit(2)
