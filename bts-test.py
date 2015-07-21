#!/usr/bin/env python
import paramiko
from scpi.devices import cmd57_console as cmd57
import atexit
import argparse
import traceback


#######################
#   Tests definition
#######################
from functools import wraps


def test_bool_checker():
    return lambda val: TEST_OK if val is not None and val \
                               else TEST_FAIL


def test_val_checker(val_ok):
    return lambda val: TEST_OK if val is not None and val == val_ok \
                               else TEST_FAIL


def test_list_checker(val_ok_list):
    return lambda val: TEST_OK if val is not None and val in val_ok_list \
                               else TEST_FAIL


def test_minmax_checker(min, max):
    return lambda val: TEST_OK if val is not None and \
                                  val >= min and \
                                  val <= max \
                               else TEST_FAIL


def test_none_checker():
    return lambda val: TEST_OK

# Enable/disable debug mode
_tests_debug = 1

TEST_NA      = -1
TEST_ABORTED = 0
TEST_OK      = 1
TEST_FAIL    = 2

TEST_RESULT_NAMES = {
    TEST_NA      : "N/A",
    TEST_ABORTED : "ABORTED",
    TEST_OK      : "OK",
    TEST_FAIL    : "FAIL"
}

# TODO: Merge TEST_NAMES and TEST_CHECKS into a single class
TEST_NAMES = {
    "tester_name": "Tester device name",
    "tester_serial": "Tester system serial number",
    "tester_version": "Tester system version",
    "tester_options": "Tester installed options",
    "output_power": "TRX output power (dBm)",
    "bcch_presence": "BCCH detected",
    "burst_avg_power": "Burst avg powr (dBm)",
    "freq_error": "Frequency error (Hz)",
    "phase_err_pk": "Phase error peak (deg)",
    "phase_err_avg": "Phase error avg (deg)",
    "enable_tch_loopback": "Enabling BTS loopback mode"
}

UMSITE_TM3_PARAMS = {
    "output_power_min": 34,  # dBm
    "output_power_max": 36,  # dBm
    "freq_error": 50,  # Hz
    "phase_err_pk_min": 2.0,  # deg
    "phase_err_pk_max": 6.0,  # deg
    "phase_err_avg_min": 0.5,  # deg
    "phase_err_avg_max": 2.0,  # deg
}

TEST_CHECKS = {
    "tester_name": test_none_checker(),
    "tester_serial": test_none_checker(),
    "tester_version": test_none_checker(),
    "tester_options": test_none_checker(),
    "output_power": test_minmax_checker(
        UMSITE_TM3_PARAMS["output_power_min"],
        UMSITE_TM3_PARAMS["output_power_max"]),
    "bcch_presence": test_bool_checker(),
    "burst_avg_power": test_minmax_checker(
        UMSITE_TM3_PARAMS["output_power_min"],
        UMSITE_TM3_PARAMS["output_power_max"]),
    "freq_error": test_minmax_checker(
        -UMSITE_TM3_PARAMS["freq_error"],
        UMSITE_TM3_PARAMS["freq_error"]),
    "phase_err_pk": test_minmax_checker(
        UMSITE_TM3_PARAMS["phase_err_pk_min"],
        UMSITE_TM3_PARAMS["phase_err_pk_max"]),
    "phase_err_avg": test_minmax_checker(
        UMSITE_TM3_PARAMS["phase_err_avg_min"],
        UMSITE_TM3_PARAMS["phase_err_avg_max"]),
    "enable_tch_loopback": test_none_checker()
}


class TestResults:

    def __init__(self, checks):
        self.test_results = {}
        self.checks = checks

    def set_test_result(self, testname, result, value=None):
        self.test_results[testname] = (result, value)
        print "%40s:  %7s" % (TEST_NAMES.get(testname, testname),
                              TEST_RESULT_NAMES[result]),
        if value is not None:
            print " (%s)" % str(value)
        else:
            print

    def check_test_result(self, testname, value):
        res = self.checks[testname](value)
        self.set_test_result(testname, res, value)
        return res

    def get_test_result(self, testname):
        return self.test_results.get(testname, TEST_NA)


# class TestDependencies:

#     dep_table = {
# #        "test_bcch_presence": ("output_power",),
#         "measure_bcch": ("bcch_presence",),
#         "measure_tch_basic": ("bcch_presence",)
#     }

#     def check_test(self, name, tr):
#         deps = self.dep_table.get(name, tuple())
#         for dep in deps:
#             if tr.get_test_result(dep) != TEST_OK:
#                 return False
#         return True


def test_checker_decorator(testname):
    def real_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                val = func(*args, **kwargs)
                res = tr.check_test_result(testname, val)
            except:
                if _tests_debug:
                    traceback.print_exc()
                res = tr.set_test_result(testname, TEST_ABORTED)
            return res
        return wrapper
    return real_decorator


###############################
#   BTS control functions
###############################

class BtsControlSsh:

    helpers = ["obscvty.py", "osmobts-en-loopback.py",
               "osmobts-set-maxdly.py", "osmobts-set-slotmask.py"]

    def __init__(self, bts_ip, username='fairwaves', password='fairwaves',
                 tmpdir='/tmp/bts-test'):
        ''' Connect to a BTS and preapre it for testing '''
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(bts_ip, username=username, password=password)

        # Copy helper scripts to the BTS
        self.tmpdir = tmpdir
        stdin, stdout, stderr = self.ssh.exec_command('mkdir -p '+self.tmpdir)
        sftp = self.ssh.open_sftp()
        for f in self.helpers:
            sftp.put('helper/'+f, self.tmpdir+'/'+f)
        sftp.close()

    def bts_en_loopback(self):
        ''' Enable loopbak in the BTS '''
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-en-loopback.py')
        print stdout.readlines()

    def bts_set_slotmask(self, ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7):
        ''' Set BTS TRX0 slotmask '''
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-slotmask.py %d %d %d %d %d %d %d %d'
            % (ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7))
        print stdout.readlines()

    def bts_set_maxdly(self, val):
        ''' Set BTS TRX0 max timing advance '''
        print("BTS: setting max delay to %d." % val)
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-maxdly.py %d' % val)
        print stdout.readlines()

###############################
#   CMD57 control functions
###############################


def cmd57_init(cmd57_port):
    dev = cmd57.rs232(cmd57_port, rtscts=True)
    atexit.register(dev.quit)
    return dev


def cmd57_configure(cmd, arfcn):
    ''' Configure the CMD57 '''
    cmd.configure_man(ccch_arfcn=arfcn, tch_arfcn=arfcn,
                      tch_ts=2, tsc=7,
                      expected_power=37, tch_tx_power=-50,
                      tch_mode='PR16', tch_timing=0)
    cmd.configure_spectrum_modulation(burst_num=10)


@test_checker_decorator("tester_name")
def test_tester_id(cmd):
    id_str = cmd.identify()
    name = id_str[0]+' '+id_str[1]
    tr.check_test_result("tester_serial", id_str[2])
    tr.check_test_result("tester_version", id_str[3])
    return name


@test_checker_decorator("tester_options")
def test_tester_options(cmd):
    return " ".join(cmd.ask_installed_options())


@test_checker_decorator("output_power")
def test_output_power(cmd):
    ''' Check output power level '''
    return cmd.ask_peak_power()


@test_checker_decorator("bcch_presence")
def test_bcch_presence(cmd):
    ''' Check BCCH presence '''
    cmd.switch_to_man_bbch()
    return cmd.ask_dev_state() == "BBCH"


@test_checker_decorator("burst_avg_power")
def test_burst_avg_power(cmd):
    return cmd.ask_burst_power_avg()


@test_checker_decorator("freq_error")
def test_freq_error(cmd):
    return cmd.ask_freq_err()


@test_checker_decorator("phase_err_pk")
def test_phase_err_pk(cmd):
    return cmd.fetch_phase_err_pk()


@test_checker_decorator("phase_err_avg")
def test_phase_err_avg(cmd):
    return cmd.fetch_phase_err_rms()


@test_checker_decorator("enable_tch_loopback")
def test_enable_tch_loopback(cmd, bts):
    cmd.switch_to_man_btch()
    bts.bts_en_loopback()


def measure_ber(dev, bts):
    ''' BER measurements '''
    dev.print_ber_test_settings()
    bts.bts_en_loopback()
    dev.print_ber_test_result(True)


###############################
#   Main test run function
###############################


def run_tests():
    print("Starting tests.")

    # Collect useful information about the CMD57
    test_tester_id(cmd)
    test_tester_options(cmd)

    # TODO: Check GPS LEDs, 1pps, NMEA

    # TODO: Calibrate Tx DC offset

    # TODO: Calibrate frequency
    #calibrate_freq_error(cmd)

    # Prepare for BCCH measurements
    res = test_bcch_presence(cmd)
    if res != TEST_OK:
        return res

    # BCCH measurements
    print "Manual test - Control Channel"
    test_burst_avg_power(cmd)
    test_freq_error(cmd)
    test_phase_err_pk(cmd)
    test_phase_err_avg(cmd)

    # Prepare for TCH tests
    res = test_enable_tch_loopback(cmd, bts)
    if res != TEST_OK:
        return res

    # Phase, power profile and spectrum measurements.
    cmd.print_man_phase_freq_info(True)
    cmd.print_man_power(True)
    cmd.print_man_spectrum_modulation(True)
    cmd.print_man_spectrum_switching(True)

    # BER measurements
    #measure_ber(cmd, bts)


###############################
#   Command line args parsing
###############################


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("bts_ip", type=str, help="Tested BTS IP address")
    parser.add_argument("-p", "--cmd57-port",
                        dest='cmd57_port', type=str, default='/dev/ttyUSB0',
                        help="Serial port name for the CMD57 control "
                             "(default: /dev/ttyUSB0)")
    parser.add_argument("-a", "--arfcn",
                        type=int, default=100,
                        help="ARFCN to test")
    return parser.parse_args()


##################
#   Main
##################

#
#   Initialization
#

# Parse command line arguments
args = parse_args()

# Initialize test results structure
tr = TestResults(TEST_CHECKS)
#test_deps = TestDependencies()

# Establish ssh connection with the BTS under test
print("Establishing connection with the BTS.")
bts = BtsControlSsh(args.bts_ip, 'fairwaves', 'fairwaves')
# CMD57 has sloppy time synchronization, so burst timing can drift
# by a few symbols
bts.bts_set_maxdly(10)

# Establish connection with CMD57 and configure it
print("Establishing connection with the CMD57.")
cmd = cmd57_init(args.cmd57_port)
cmd.switch_to_man_bidl()
cmd57_configure(cmd, args.arfcn)

#
#   Test execution
#

run_tests()
