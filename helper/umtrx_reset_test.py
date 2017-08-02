#!/usr/bin/env python3
import os
import sys
import time
import subprocess

LOG='/var/log/umtrx-log/current'

PRODUCTION=(
	"SPI Flash has been initialized",
	"Checking for valid production FPGA image...",
	"Valid production FPGA image found. Attempting to boot.",
	"SPI Flash has been initialized",
	"Valid production firmware found. Loading...",
	"Finished loading. Starting image.",
	"TxRx-UHD-ZPU",
	"LMS1 chip version = 0x22",
	"LMS2 chip version = 0x22",
	"eth link changed: speed = 1000")

SAFE=(
	"SPI Flash has been initialized",
	"Starting UmTRX in safe mode. Loading safe firmware.",
	"LMS1 chip version = 0x22",
	"LMS2 chip version = 0x22",
	"eth link changed: speed = 1000")

def check_events(f, events, timeout):
	start = time.time()
	pos = 0
	log = []

	while time.time() - start < timeout:
		for l in f:
			#print (l)
			log.append(l)
			if l.find(events[pos]) >= 0:
				print ("FOUND: %s" % events[pos])
				pos += 1
				if pos == len(events):
					return True
		time.sleep(1)

	print ("FAILED!!!: %s" % str(log))
	return False


# Use 'latin-1' here, because we can get some arbitrary trash and we don't want
# to fail because exceptions due to failure to convert to UTF-8 (default encoding).
# The solution is described here:
# http://python-notes.curiousefficiency.org/en/latest/python3/text_file_processing.html#files-in-an-ascii-compatible-encoding-best-effort-is-acceptable
# In short: "use the 'latin-1' encoding to map byte values directly to the first
# 256 Unicode code points. This is the closest equivalent Python 3 offers to
# the permissive Python 2 text handling model.
with open(LOG, 'rt', encoding="latin-1") as f:
	# empty buffer
	#for l in f:
	#	print ("Flashing out: %s", l)
	#	pass	
	f.seek(0,2)

	ret = subprocess.call("umtrx-safe-reset.sh", shell=True)
	if ret != 0:
		print ("Unable to execute umtrx-safe-reset.sh")
		sys.exit(1)

	check_events(f, SAFE, 15) or sys.exit(2)

	f.seek(0,2)
	ret = subprocess.call("umtrx-reset.sh", shell=True)
	if ret != 0:
		print ("Unable to execute umtrx-safe-reset.sh")
		sys.exit(3)

	time.sleep(30)
	check_events(f, PRODUCTION, 15) or sys.exit(4)
	
print("SUCCESS")
sys.exit(0)

