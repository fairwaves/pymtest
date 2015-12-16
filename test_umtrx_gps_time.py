import os
import sys
import time
import subprocess
import fcntl
import time
import datetime

DEV='/var/run/gpsd.device'
DELAY=3

with open(DEV, 'rt') as f:
	fd = f.fileno()
	flag = fcntl.fcntl(fd, fcntl.F_GETFD)
	fcntl.fcntl(fd, fcntl.F_SETFD, flag | os.O_NONBLOCK)
	
	while True:
		l = os.read(fd, 131072)
		if len(l) <= 2:
			break
	
	time.sleep(DELAY)
	dt = datetime.datetime.today()

	ticks=[]

	for l in os.read(fd, 65536).decode('utf-8').split():
		if l.startswith("$GPZDA"):
			ticks.append(l)

	if len(ticks) < 1:
		sys.exit(1)	

	p=ticks[-1].split(',')
	if len(p) < 6:
		if len(ticks) > 2:
			p=ticks[-2].split(',')
		else:
			sys.exit(3)

	dt2 = datetime.datetime(int(p[4]), int(p[3]), int(p[2]), int(float(p[1]) / 10000), int((float(p[1]) % 10000) / 100), int(float(p[1]) % 100))

	#print (dt, dt2, dt - dt2)
	delta = (dt - dt2).total_seconds()
	print ("%s%+f: Got %d ticks; last was %s" % (dt, delta, len(ticks), ticks[-1]))

	if abs(delta) < 45:
		print("SUCCESS")
		sys.exit(0)

sys.exit(2)

