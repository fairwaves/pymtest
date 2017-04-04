#!/usr/bin/env python
import sys
import os
import paramiko
import time
from scpi.devices import cmd57
import atexit


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.0.0.21', username='fairwaves')


def move_bursts(dir):
    stdin, stdout, stderr = ssh.exec_command(
        '/usr/local/src/fairwaves-tools/scripts/osmo-trx/' +
        'transceiver_dump_bursts.py')
    stdout.readlines()
    stdin, stdout, stderr = ssh.exec_command(
        'cd ~/osmo-trx-master/Transceiver52M/rec ' +
        '; ls *.fc | wc -l ; DIR=%s ; mkdir $DIR ; mv *.fc $DIR' % dir)
    print stdout.readlines()


def dump_bursts(pwr):
    dirname = "%.1fdBm-PSR16" % (-pwr)
    print dirname
    dev.set_bts_tch_tx_power(pwr)
    time.sleep(0.1)
    move_bursts(dirname)


if len(sys.argv) < 2:
    print "Usage:"
    print "  python ssh-dump-bursts.py /dev/ttyUSB0"
    sys.exit(1)

dev = cmd57.rs232(sys.argv[1], rtscts=True)
atexit.register(dev.quit)

dev.switch_to_man_bidl()
dev.configure_man(ccch_arfcn=100, tch_arfcn=100, tch_ts=2, tsc=7,
                  expected_power=37, tch_tx_power=-50,
                  tch_mode='PR16', tch_timing=0)

# print_sys_info(dev)
# print_sys_config(dev)
# print_man_config(dev)

dev.switch_to_man_bidl()
dev.switch_to_man_btch()

start_power = -100.0
stop_power = -108.0
step_power = -0.1
for pwr in map(lambda x: x / 10.0, range(int(start_power * 10),
               int((stop_power + step_power) * 10), int(step_power * 10))):
    dump_bursts(pwr)
