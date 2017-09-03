#!/usr/bin/env python
import supervise
from datetime import timedelta

# Maximum numbe of seconds between system uptime and service uptime
max_uptime_difference = 60

# TODO: get a list of services automatically
service_dir = "/etc/service/"
service_names = ["osmo-trx", "osmo-bts", "osmo-nitb", "lcr"]

def uptime():
    with open('/proc/uptime', 'r') as f:
        return float(f.readline().split()[0])

def print_service_status(name, s, status):
    print("%s %s %s %s %d %+d" % (name, status, s._status2str(s.status), s._action2str(s.action), s.uptime, uptime_seconds-s.uptime))

services = {name: supervise.Service(service_dir+name) for name in service_names}
uptime_seconds = uptime()
statuses = {name: s.status() for (name, s) in services.iteritems()}

print("uptime: %d seconds" % uptime_seconds)
print("uptime: %s" % str(timedelta(seconds = uptime_seconds)))
total_ok = True
for (name, s) in statuses.iteritems():
    if s.status == supervise.STATUS_UP and uptime_seconds-s.uptime < max_uptime_difference:
        print_service_status(name, s, "OK")
    else:
        total_ok = False
        print_service_status(name, s, "ERROR")
print("Total: %s" % ("OK" if total_ok else "ERROR"))
