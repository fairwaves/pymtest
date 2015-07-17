#!/usr/bin/env python
import paramiko
from scpi.devices import cmd57_console as cmd57
import atexit
import argparse


###############################
#   BTS control functions
###############################

def bts_init(bts_ip, username='fairwaves'):
    ''' Connect to a BTS and preapre it for testing '''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(bts_ip, username=username)

    # CMD57 has sloppy time synchronization, so burst timing can drift
    # by a few symbols
    bts_set_maxdly(ssh, 10)

    return ssh


def bts_en_loopback(ssh):
    ''' Enable loopbak in the BTS '''
    stdin, stdout, stderr = ssh.exec_command('./osmobts-en-loopback.py')
    stdout.readlines()


def bts_set_slotmask(ssh, ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7):
    ''' Set BTS TRX0 slotmask '''
    stdin, stdout, stderr = ssh.exec_command(
      './osmobts-set-slotmask.py %d %d %d %d %d %d %d %d'
      % (ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7))
    print stdout.readlines()


def bts_set_maxdly(ssh, val):
    ''' Set BTS TRX0 max timing advance '''
    stdin, stdout, stderr = ssh.exec_command('./osmobts-set-maxdly.py %d' % val)
    stdout.readlines()

###############################
#   CMD57 control functions
###############################


def cmd57_init(cmd57_port):
    dev = cmd57.rs232(cmd57_port, rtscts=True)
    atexit.register(dev.quit)
    return dev


def cmd57_configure(arfcn):
    ''' Configure the CMD57 '''
    dev.configure_man(ccch_arfcn=arfcn, tch_arfcn=arfcn,
                      tch_ts=2, tsc=7,
                      expected_power=37, tch_tx_power=-50,
                      tch_mode='PR16', tch_timing=0)
    dev.configure_spectrum_modulation(burst_num=10)


def measure_bcch(dev):
    ''' BBCH measurements '''
    dev.print_man_bbch_info(True)


def measure_tch_basic(dev):
    ''' TCH basic measurements '''
    # TODO: changing slotmask breaks things. We'll live without it so far.
    #       CMD57 will complain about failed mask, but we can check it
    #       ourselves (this is a todo for future).
#    bts_set_slotmask(ssh, 1, 0, 1, 0, 1, 0, 1, 0)
    dev.print_man_btch_info(True)
#    bts_set_slotmask(ssh, 1, 1, 1, 1, 1, 1, 1, 1)


def measure_tch_adv(dev):
    ''' Phase, power profile and spectrum measurements. '''
    dev.print_man_phase_freq_info(True)
    dev.print_man_power(True)
    dev.print_man_spectrum_modulation(True)
    dev.print_man_spectrum_switching(True)


def measure_ber(dev):
    ''' BER measurements '''
    dev.print_ber_test_settings()
    dev.print_ber_test_result(True)

##################
#   Main
##################

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("bts_ip", type=str, help="Tested BTS IP address")
parser.add_argument("-p", "--cmd57-port",
                    dest='cmd57_port', type=str, default='/dev/ttyUSB0',
                    help="Serial port name for the CMD57 control "
                         "(default: /dev/ttyUSB0)")
parser.add_argument("-a", "--arfcn",
                    type=int, default=100,
                    help="ARFCN to test")
args = parser.parse_args()

# Establish ssh connection with the BTS
ssh = bts_init(args.bts_ip, 'fairwaves')

# Open the CMD57 control port
dev = cmd57_init(args.cmd57_port)

# Configure the CMD57
dev.switch_to_man_bidl()
cmd57_configure(args.arfcn)

# BBCH measurements
dev.switch_to_man_bbch()
measure_bcch(dev)

# Switch to TCH
dev.switch_to_man_btch()
bts_en_loopback(ssh)

# BTCH measurements
measure_tch(dev)

# Phase, power profile and spectrum measurements.
measure_tch_adv(dev)

# BER measurements
measure_ber(dev)
