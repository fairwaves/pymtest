#!/usr/bin/env python
import paramiko
from scpi.devices import cmd57_console as cmd57
import atexit
import argparse
import traceback
import re
import json
import os, sys, select  # for stdin flush

UMSITE_TM3_VGA2_DEF = 22
UMSITE_TM3_DCDC_DEF = 190

UMTRX_VGA2_DEF = UMSITE_TM3_VGA2_DEF
UMTRX_DCDC_DEF = UMSITE_TM3_DCDC_DEF
UMTRX_DCDC_MAX = 255

#######################
#   Tests definition
#######################
from functools import wraps
import time


def test_none_checker():
    return lambda val: TEST_OK if val is not None \
                               else TEST_FAIL


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


def test_ignore_checker():
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
    "bts_uname": "BTS system information",
    "umtrx_serial": "UmTRX serial number",
    "umtrx_autocalibrate": "UmTRX autocalibration",
    "tester_name": "Tester device name",
    "tester_serial": "Tester system serial number",
    "tester_version": "Tester system version",
    "tester_options": "Tester installed options",
    "bcch_presence": "BCCH detected",
    "burst_power_peak": "TRX output power (dBm)",
    "burst_power_avg": "Burst avg power (dBm)",
    "burst_power_array": "Burst power array (dBm)",
    "freq_error": "Frequency error (Hz)",
    "phase_err_array": "Phase error array (deg)",
    "phase_err_pk": "Phase error peak (deg)",
    "phase_err_avg": "Phase error avg (deg)",
    "spectrum_modulation_offsets": "Modulation spectrum measurement offsets (kHz)",
    "spectrum_modulation_tolerance_abs": "Modulation spectrum absolute tolerance mask (dBm)",
    "spectrum_modulation_tolerance_rel": "Modulation spectrum relative tolerance mask (dBc)",
    "spectrum_modulation": "Modulation spectrum measured (dBc)",
    "spectrum_modulation_match": "Modulation spectrum match",
    "spectrum_switching_offsets": "Switching spectrum measurement offsets (kHz)",
    "spectrum_switching_tolerance_abs": "Switching spectrum absolute tolerance mask (dBm)",
    "spectrum_switching_tolerance_rel": "Switching spectrum relative tolerance mask (dBc)",
    "spectrum_switching": "Switching spectrum measured (dBc)",
    "spectrum_switching_match": "Switching spectrum match",
    "ber_used_ts_power": "Used TS power (dBm)",
    "ber_unused_ts_power": "Unused TS power (dBm)",
    "ber_frames_num": "Frames to send",
    "ber_max_test_time": "Test time",
    "ber_abort_condition": "Abort condition",
    "ber_holdoff_time": "Hold-off time",
    "ber_limit_class_1b": "Class Ib bit errors tolerance (%)",
    "ber_max_class_1b_samples": "Class Ib bit errors max number",
    "ber_limit_class_2": "Class II bit errors tolerance (%)",
    "ber_max_class_2_samples": "Class II bit errors max number",
    "ber_limit_erased_frames": "Erased frames tolerance (%)",
    "ber_max_erased_frames_samples": "Erased frames max number",
    "ber_test_result": "BER test result",
    "ber_class_1b_events": "Class Ib bit error events",
    "ber_class_1b_ber": "Class Ib bit error rate (%)",
    "ber_class_1b_rber": "Class Ib bit residual error rate (%)",
    "ber_class_2_events": "Class II bit error events",
    "ber_class_2_ber": "Class II bit error rate (%)",
    "ber_class_2_rber": "Class II bit residual error rate (%)",
    "ber_erased_events": "Erased frame events",
    "ber_erased_fer": "Erased frame rate (%)",
    "ber_crc_errors": "CRC errors",
    "enable_tch_loopback": "Enabling BTS loopback mode",
    "power_vswr_vga2": "Power&VSWR vs VGA2",
    "power_vswr_dcdc": "Power&VSWR vs DCDC control",
    "vswr_vga2": "VSWR vs VGA2"
}

UMSITE_TM3_PARAMS = {
    "burst_power_peak_min": 34,  # dBm
    "burst_power_peak_max": 36,  # dBm
    "freq_error": 50,  # Hz
    "phase_err_pk_min": -10.0,  # deg
    "phase_err_pk_max":  10.0,  # deg
    "phase_err_avg_min": 0.5,  # deg
    "phase_err_avg_max": 2.0,  # deg
}

TEST_CHECKS = {
    "bts_uname": test_ignore_checker(),
    "umtrx_serial": test_none_checker(),
    "umtrx_autocalibrate": test_bool_checker(),
    "tester_name": test_ignore_checker(),
    "tester_serial": test_ignore_checker(),
    "tester_version": test_ignore_checker(),
    "tester_options": test_ignore_checker(),
    "bcch_presence": test_bool_checker(),
    "burst_power_peak": test_minmax_checker(
        UMSITE_TM3_PARAMS["burst_power_peak_min"],
        UMSITE_TM3_PARAMS["burst_power_peak_max"]),
    "burst_power_avg": test_minmax_checker(
        UMSITE_TM3_PARAMS["burst_power_peak_min"],
        UMSITE_TM3_PARAMS["burst_power_peak_max"]),
    "burst_power_array": test_ignore_checker(),
    "freq_error": test_minmax_checker(
        -UMSITE_TM3_PARAMS["freq_error"],
        UMSITE_TM3_PARAMS["freq_error"]),
    "phase_err_array": test_ignore_checker(),
    "phase_err_pk": test_minmax_checker(
        UMSITE_TM3_PARAMS["phase_err_pk_min"],
        UMSITE_TM3_PARAMS["phase_err_pk_max"]),
    "phase_err_avg": test_minmax_checker(
        UMSITE_TM3_PARAMS["phase_err_avg_min"],
        UMSITE_TM3_PARAMS["phase_err_avg_max"]),
    "spectrum_modulation_offsets": test_ignore_checker(),
    "spectrum_modulation_tolerance_abs": test_ignore_checker(),
    "spectrum_modulation_tolerance_rel": test_ignore_checker(),
    "spectrum_modulation": test_ignore_checker(),
    "spectrum_modulation_match": test_val_checker("MATC"),
    "spectrum_switching_offsets": test_ignore_checker(),
    "spectrum_switching_tolerance_abs": test_ignore_checker(),
    "spectrum_switching_tolerance_rel": test_ignore_checker(),
    "spectrum_switching": test_ignore_checker(),
    "spectrum_switching_match": test_ignore_checker(),
    "ber_used_ts_power": test_ignore_checker(),
    "ber_unused_ts_power": test_ignore_checker(),
    "ber_frames_num": test_ignore_checker(),
    "ber_max_test_time": test_ignore_checker(),
    "ber_abort_condition": test_ignore_checker(),
    "ber_holdoff_time": test_ignore_checker(),
    "ber_limit_class_1b": test_ignore_checker(),
    "ber_max_class_1b_samples": test_ignore_checker(),
    "ber_limit_class_2": test_ignore_checker(),
    "ber_max_class_2_samples": test_ignore_checker(),
    "ber_limit_erased_frames": test_ignore_checker(),
    "ber_max_erased_frames_samples": test_ignore_checker(),
    "ber_test_result": test_val_checker("PASS"),
    "ber_class_1b_events": test_ignore_checker(),
    "ber_class_1b_ber": test_ignore_checker(),
    "ber_class_1b_rber": test_ignore_checker(),
    "ber_class_2_events": test_ignore_checker(),
    "ber_class_2_ber": test_ignore_checker(),
    "ber_class_2_rber": test_ignore_checker(),
    "ber_erased_events": test_ignore_checker(),
    "ber_erased_fer": test_ignore_checker(),
    "ber_crc_errors": test_ignore_checker(),
    "enable_tch_loopback": test_ignore_checker(),
    "power_vswr_vga2": test_none_checker(),
    "power_vswr_dcdc": test_none_checker(),
    "vswr_vga2": test_none_checker()
}


class TestResults:

    def __init__(self, checks):
        self.test_results = {}
        self.checks = checks
        self.scope = 'global'

    def set_test_scope(self, scope):
        self.scope = scope

    def _get_scope_subtree(self):
        return self.test_results.setdefault(self.scope, {})

    def set_test_result(self, testname, result, value=None):
        t = time.time()
        self._get_scope_subtree()[testname] = (t, result, value)
        print "[%s] %50s:  %7s" % (
            time.strftime("%d %B %Y %H:%M:%S", time.localtime(t)),
            TEST_NAMES.get(testname, testname),
            TEST_RESULT_NAMES[result]),
        if value is not None:
            print " (%s)" % str(value)
        else:
            print
        return result

    def check_test_result(self, testname, value):
        res = self.checks[testname](value)
        self.set_test_result(testname, res, value)
        return res

    def get_test_result(self, testname):
        return self._get_scope_subtree().get(testname, (0, TEST_NA, None))

    def json(self):
        return json.dumps(self.test_results,
                          indent=4, separators=(',', ': '))


# class TestDependencies:

#     dep_table = {
# #        "test_bcch_presence": ("burst_power_peak",),
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
                res = TEST_ABORTED
                tr.set_test_result(testname, res)
            return res
        return wrapper
    return real_decorator


###############################
#   BTS control functions
###############################

class BtsControlSsh:

    helpers = ["obscvty.py", "osmobts-en-loopback.py",
               "osmobts-set-maxdly.py", "osmobts-set-slotmask.py",
               "osmo-trx-primary-trx.py", "umtrx_set_dcdc_r.py",
               "umtrx_get_vswr_sensors.py",
               # TODO: Move this from helpers to packages
               "umtrx_property_tree.py",
               "umtrx_ctrl.py", "umtrx_lms.py"]

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

    def _tee(self, stream, filename):
        ''' Write lines from the stream to the file and return the lines '''
        lines = stream.readlines()
        f = file(filename, 'w')
        f.writelines(lines)
        f.close()
        return lines

    def get_uname(self):
        ''' Get uname string '''
        stdin, stdout, stderr = self.ssh.exec_command('uname -a')
        return stdout.readline().strip()

    def trx_set_primary(self, num):
        ''' Set primary TRX '''
        print "Setting primary TRX to TRX%d" % num
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'sudo python osmo-trx-primary-trx.py %d' % num)
        print stderr.readlines() + stdout.readlines()

    def bts_en_loopback(self):
        ''' Enable loopbak in the BTS '''
        print "Enabling BTS loopback"
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-en-loopback.py')
        print stderr.readlines() + stdout.readlines()

    def bts_set_slotmask(self, ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7):
        ''' Set BTS TRX0 slotmask '''
        print "Setting BTS slotmask"
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-slotmask.py %d %d %d %d %d %d %d %d'
            % (ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7))
        print stderr.readlines() + stdout.readlines()

    def bts_set_maxdly(self, val):
        ''' Set BTS TRX0 max timing advance '''
        print("BTS: setting max delay to %d." % val)
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-maxdly.py %d' % val)
        print stderr.readlines() + stdout.readlines()

    def umtrx_set_dcdc_r(self, val):
        ''' Set UmTRX DCDC control register value '''
#        print("UmTRX: setting DCDC control register to %d." % val)
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_set_dcdc_r.py %d' % val)
        stdout.readlines()

    def umtrx_set_tx_vga2(self, chan, val):
        ''' Set UmTRX Tx VGA2 gain '''
#        print("UmTRX: setting UmTRX Tx VGA2 gain for chan %d to %d."
#              % (chan, val))
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_lms.py --lms %d --lms-set-tx-vga2-gain %d'
            % (chan, val))
        stdout.readlines()

    def umtrx_get_vswr_sensors(self, chan):
        ''' Read UmTRX VPR and VPF sensors '''
        stdin, stdout, stderr = self.ssh.exec_command(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_get_vswr_sensors.py')
        res = [float(x.strip()) for x in stdout.readlines()]
        start = (chan-1)*2
        return res[start:start+2]

    def start_runit_service(self, service):
        ''' Start a runit controlled service '''
        print("Starting '%s' service." % service)
        stdin, stdout, stderr = self.ssh.exec_command(
            'sudo sv start %s' % service)
        # TODO: Check result
        print stderr.readlines() + stdout.readlines()

    def stop_runit_service(self, service):
        ''' Stop a runit controlled service '''
        print("Stopping '%s' service." % service)
        stdin, stdout, stderr = self.ssh.exec_command(
            'sudo sv stop %s' % service)
        # TODO: Check result
        print stderr.readlines() + stdout.readlines()

    def restart_runit_service(self, service):
        ''' Restart a runit controlled service '''
        print("Restarting '%s' service." % service)
        stdin, stdout, stderr = self.ssh.exec_command(
            'sudo sv restart %s' % service)
        # TODO: Check result
        print stderr.readlines() + stdout.readlines()

    def get_umtrx_eeprom_val(self, name):
        ''' Read UmTRX serial from EEPROM.
            All UHD apps should be stopped at the time of reading. '''
        stdin, stdout, stderr = self.ssh.exec_command(
            '/usr/lib/uhd/utils/usrp_burn_mb_eeprom --values "serial"')
        eeprom_val = re.compile(r'    EEPROM \["'+name+r'"\] is "(.*)"')
        for s in stdout.readlines():
            match = eeprom_val.match(s)
            if match is not None:
                return match.group(1)
        return None

    def umtrx_autocalibrate(self, preset, filename_stdout, filename_stderr):
        ''' Run UmTRX autocalibration for the selected band.
            preset - One or more of the following space seprated values:
                     GSM850, EGSM900 (same as GSM900),
                     GSM1800 (same as DCS1800), GSM1900 (same as PCS1900)
            All UHD apps should be stopped at the time of executing. '''
        stdin, stdout, stderr = self.ssh.exec_command(
            'sudo umtrx_auto_calibration %s' % preset)
        # TODO: Check result
        lines = self._tee(stdout, filename_stdout)
        self._tee(stderr, filename_stderr)
        line_re = re.compile(r'Calibration type .* side . from .* to .*: ([A-Z]+)')
        for l in lines:
            match = line_re.match(l)
            if match is not None:
                if match.group(1) != 'SUCCESS':
                    return False
        return True

###############################
#   non-CMD57 based tests
###############################


@test_checker_decorator("bts_uname")
def bts_read_uname(bts):
    return bts.get_uname()


@test_checker_decorator("umtrx_serial")
def bts_read_umtrx_serial(bts):
    return bts.get_umtrx_eeprom_val("serial")


@test_checker_decorator("umtrx_autocalibrate")
def bts_umtrx_autocalibrate(bts, preset, filename_stdout, filename_stderr):
    return bts.umtrx_autocalibrate(preset, filename_stdout, filename_stderr)

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
                      expected_power=37, tch_tx_power=-60,
                      tch_mode='PR16', tch_timing=0)
    cmd.configure_spectrum_modulation(burst_num=10)

###############################
#   CMD57 based tests
###############################


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


@test_checker_decorator("burst_power_peak")
def test_burst_power_peak(cmd):
    ''' Check output power level '''
    return cmd.ask_peak_power()


def test_burst_power_peak_wait(cmd, timeout):
    ''' Wait for output power level '''
    res = TEST_NA
    t = time.time()
    while res != TEST_OK and time.time()-t < timeout:
        res = test_burst_power_peak(cmd)
    return res


@test_checker_decorator("bcch_presence")
def test_bcch_presence(cmd):
    ''' Check BCCH presence '''
    cmd.switch_to_man_bbch()
    return cmd.ask_dev_state() == "BBCH"

#
# Burst power, phase and frequency tests
#


@test_checker_decorator("burst_power_avg")
def test_burst_power_avg(cmd):
    return cmd.ask_burst_power_avg()


@test_checker_decorator("burst_power_array")
def test_burst_power_array(cmd):
    return cmd.ask_burst_power_arr()


@test_checker_decorator("freq_error")
def test_freq_error(cmd):
    return cmd.ask_freq_err()


@test_checker_decorator("phase_err_array")
def test_phase_err_array(cmd):
    return cmd.ask_phase_err_arr()


@test_checker_decorator("phase_err_pk")
def test_phase_err_pk(cmd):
    return cmd.fetch_phase_err_pk()


@test_checker_decorator("phase_err_avg")
def test_phase_err_avg(cmd):
    return cmd.fetch_phase_err_rms()

#
# Spectrum tests
#


@test_checker_decorator("spectrum_modulation_offsets")
def test_spectrum_modulation_offsets(cmd):
    return cmd.fetch_spectrum_modulation_offsets()


@test_checker_decorator("spectrum_modulation_tolerance_abs")
def test_spectrum_modulation_tolerance_abs(cmd):
    return cmd.ask_spectrum_modulation_tolerance_abs()


@test_checker_decorator("spectrum_modulation_tolerance_rel")
def test_spectrum_modulation_tolerance_rel(cmd):
    return cmd.ask_spectrum_modulation_tolerance_rel()


@test_checker_decorator("spectrum_modulation")
def test_spectrum_modulation(cmd):
    return cmd.ask_spectrum_modulation()


@test_checker_decorator("spectrum_modulation_match")
def test_spectrum_modulation_match(cmd):
    return cmd.ask_spectrum_modulation_match()


@test_checker_decorator("spectrum_switching_offsets")
def test_spectrum_switching_offsets(cmd):
    return cmd.fetch_spectrum_switching_offsets()


@test_checker_decorator("spectrum_switching_tolerance_abs")
def test_spectrum_switching_tolerance_abs(cmd):
    return cmd.ask_spectrum_switching_tolerance_abs()


@test_checker_decorator("spectrum_switching_tolerance_rel")
def test_spectrum_switching_tolerance_rel(cmd):
    return cmd.ask_spectrum_switching_tolerance_rel()


@test_checker_decorator("spectrum_switching")
def test_spectrum_switching(cmd):
    return cmd.ask_spectrum_switching()


@test_checker_decorator("spectrum_switching_match")
def test_spectrum_switching_match(cmd):
    return cmd.ask_spectrum_switching_match()

#
# BER test settings
#


@test_checker_decorator("ber_used_ts_power")
def test_ber_used_ts_power(cmd):
    return cmd.ask_ber_used_ts_power()


@test_checker_decorator("ber_unused_ts_power")
def test_ber_unused_ts_power(cmd):
    return cmd.ask_ber_unused_ts_power()


@test_checker_decorator("ber_frames_num")
def test_ber_frames_num(cmd):
    return cmd.ask_ber_frames_num()


@test_checker_decorator("ber_max_test_time")
def test_ber_max_test_time(cmd):
    return cmd.ask_ber_max_test_time()


@test_checker_decorator("ber_abort_condition")
def test_ber_abort_condition(cmd):
    return cmd.ask_ber_abort_cond()


@test_checker_decorator("ber_holdoff_time")
def test_ber_holdoff_time(cmd):
    return cmd.ask_ber_holdoff_time()


@test_checker_decorator("ber_limit_class_1b")
def test_ber_limit_class_1b(cmd):
    return cmd.ask_ber_limit_class_1b()


@test_checker_decorator("ber_max_class_1b_samples")
def test_ber_max_class_1b_samples(cmd):
    return cmd.ask_ber_max_class_1b_samples()


@test_checker_decorator("ber_limit_class_2")
def test_ber_limit_class_2(cmd):
    return cmd.ask_ber_limit_class_2()


@test_checker_decorator("ber_max_class_2_samples")
def test_ber_max_class_2_samples(cmd):
    return cmd.ask_ber_max_class_2_samples()


@test_checker_decorator("ber_limit_erased_frames")
def test_ber_limit_erased_frames(cmd):
    return cmd.ask_ber_limit_erased_frames()


@test_checker_decorator("ber_max_erased_frames_samples")
def test_ber_max_erased_frames_samples(cmd):
    return cmd.ask_ber_max_erased_frames_samples()

#
# BER test results
#


@test_checker_decorator("ber_test_result")
def test_ber_test_result(cmd):
    return cmd.read_ber_test_result()


@test_checker_decorator("ber_class_1b_events")
def test_ber_class_1b_events(cmd):
    return cmd.fetch_ber_class_1b_events()


@test_checker_decorator("ber_class_1b_ber")
def test_ber_class_1b_ber(cmd):
    return cmd.fetch_ber_class_1b_ber()


@test_checker_decorator("ber_class_1b_rber")
def test_ber_class_1b_rber(cmd):
    return cmd.fetch_ber_class_1b_rber()


@test_checker_decorator("ber_class_2_events")
def test_ber_class_2_events(cmd):
    return cmd.fetch_ber_class_2_events()


@test_checker_decorator("ber_class_2_ber")
def test_ber_class_2_ber(cmd):
    return cmd.fetch_ber_class_2_ber()


@test_checker_decorator("ber_class_2_rber")
def test_ber_class_2_rber(cmd):
    return cmd.fetch_ber_class_2_rber()


@test_checker_decorator("ber_erased_events")
def test_ber_erased_events(cmd):
    return cmd.fetch_ber_erased_events()


@test_checker_decorator("ber_erased_fer")
def test_ber_erased_fer(cmd):
    return cmd.fetch_ber_erased_fer()


@test_checker_decorator("ber_crc_errors")
def test_ber_crc_errors(cmd):
    return cmd.fetch_ber_crc_errors()

#
# Power calibration
#


@test_checker_decorator("power_vswr_vga2")
def test_power_vswr_vga2(cmd, bts, chan):
    try:
        print "Testing power&VSWR vs VGA2"
        print "VGA2\tPk power\tAvg power\tVPF\tVPR"
        res = []
        for vga2 in range(26):
            bts.umtrx_set_tx_vga2(chan, vga2)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, power_pk, power_avg, vpf, vpr))
            print("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for vga2 in range(25, -1, -1):
            bts.umtrx_set_tx_vga2(chan, vga2)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, power_pk, power_avg, vpf, vpr))
            print("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_tx_vga2(chan, UMTRX_VGA2_DEF)


@test_checker_decorator("vswr_vga2")
def test_vswr_vga2(bts, chan):
    try:
        print "Testing VSWR vs VGA2"
        print "VGA2\tVPF\tVPR"
        res = []
        for vga2 in range(26):
            bts.umtrx_set_tx_vga2(chan, vga2)
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, vpf, vpr))
            print("%d\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for vga2 in range(25, -1, -1):
            bts.umtrx_set_tx_vga2(chan, vga2)
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, vpf, vpr))
            print("%d\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_tx_vga2(chan, UMTRX_VGA2_DEF)


@test_checker_decorator("power_vswr_dcdc")
def test_power_vswr_dcdc(cmd, bts, chan):
    try:
        print "Testing power&VSWR vs DCDC control"
        print "DCDC_R\tPk power\tAvg power\tVPF\tVPR"
        res = []
        for dcdc in range(UMTRX_DCDC_MAX+1):
            bts.umtrx_set_dcdc_r(dcdc)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((dcdc, power_pk, power_avg, vpf, vpr))
            print("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for dcdc in range(UMTRX_DCDC_MAX, -1, -1):
            bts.umtrx_set_dcdc_r(dcdc)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((dcdc, power_pk, power_avg, vpf, vpr))
            print("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_dcdc_r(UMTRX_DCDC_DEF)


#
# Helpers
#


@test_checker_decorator("enable_tch_loopback")
def test_enable_tch_loopback(cmd, bts):
    cmd.switch_to_man_btch()
    bts.bts_en_loopback()


###############################
#   Main test run function
###############################


def run_bts_tests():
    print("Starting BTS tests.")

    # Stop osmo-trx to unlock UmTRX
    bts.stop_runit_service("osmo-trx")

    # Collect information about the BTS
    bts_read_uname(bts)
    bts_read_umtrx_serial(bts)

    # Autocalibrate UmTRX
    bts_umtrx_autocalibrate(bts, "GSM900", "calibration.log", "calibration.err.log")

    # Start osmo-trx again
    bts.start_runit_service("osmo-trx")


def run_cmd57_info():
    print("Collecting CMD57 information.")

    # Collect useful information about the CMD57
    test_tester_id(cmd)
    test_tester_options(cmd)


def run_tch_sync():
    print("Starting Tx tests.")

    # Make sure we start in idle mode
    cmd.switch_to_idle()

    # Measure peak power before everything else
    test_burst_power_peak_wait(cmd, 20)

    # Prepare for TCH tests
    return test_enable_tch_loopback(cmd, bts)


def run_tx_tests():
    print("Starting Tx tests.")

    # Burst power measurements
    test_burst_power_avg(cmd)
    test_burst_power_array(cmd)

    # Phase and frequency measurements
    test_freq_error(cmd)
    test_phase_err_array(cmd)
    test_phase_err_pk(cmd)  # fetches calculated value only
    test_phase_err_avg(cmd)  # fetches calculated value only

    # Modulation spectrum measurements
    test_spectrum_modulation_offsets(cmd)
    test_spectrum_modulation_tolerance_abs(cmd)
    test_spectrum_modulation_tolerance_rel(cmd)
    test_spectrum_modulation(cmd)
    test_spectrum_modulation_match(cmd)

    # Switching spectrum measurements
    test_spectrum_switching_offsets(cmd)
    test_spectrum_switching_tolerance_abs(cmd)
    test_spectrum_switching_tolerance_rel(cmd)
    test_spectrum_switching(cmd)
    test_spectrum_switching_match(cmd)


def run_ber_tests():
    print("Starting BER tests.")

    # BER test settings
    test_ber_used_ts_power(cmd)
    test_ber_unused_ts_power(cmd)
    test_ber_frames_num(cmd)
    test_ber_max_test_time(cmd)
    test_ber_abort_condition(cmd)
    test_ber_holdoff_time(cmd)
    test_ber_limit_class_1b(cmd)
    test_ber_max_class_1b_samples(cmd)
    test_ber_limit_class_2(cmd)
    test_ber_max_class_2_samples(cmd)
    test_ber_limit_erased_frames(cmd)
    test_ber_max_erased_frames_samples(cmd)

    # BER test result
    test_ber_test_result(cmd)
    test_ber_class_1b_events(cmd)
    test_ber_class_1b_ber(cmd)
    test_ber_class_1b_rber(cmd)
    test_ber_class_2_events(cmd)
    test_ber_class_2_ber(cmd)
    test_ber_class_2_rber(cmd)
    test_ber_erased_events(cmd)
    test_ber_erased_fer(cmd)
    test_ber_crc_errors(cmd)

    # Nice printout, just for the screen
    cmd.print_ber_test_settings()
    cmd.print_ber_test_result(False)


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
#   UI functions
##################


def ui_ask(text):
    # Note: this flush code works under *nix OS only
    while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0])>0:
        os.read(sys.stdin.fileno(), 4096)

    print
    print "~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    val = raw_input(text+" ")
    print "~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    print
    return val


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

#
#   BTS tests
#

# Establish ssh connection with the BTS under test
print("Establishing connection with the BTS.")
bts = BtsControlSsh(args.bts_ip, 'fairwaves', 'fairwaves')
# CMD57 has sloppy time synchronization, so burst timing can drift
# by a few symbols
bts.bts_set_maxdly(10)

tr.set_test_scope("system")
run_bts_tests()

#
#   CMD57 tests
#

# Establish connection with CMD57 and configure it
print("Establishing connection with the CMD57.")
cmd = cmd57_init(args.cmd57_port)
cmd.switch_to_man_bidl()
cmd57_configure(cmd, args.arfcn)

try:
    for trx in [1, 2]:
        resp = ui_ask("Connect CMD57 to the TRX%d." % trx)
        if resp != 's':
            tr.set_test_scope("TRX%d" % trx)
            bts.trx_set_primary(trx)
            bts.restart_runit_service("osmo-trx")
            run_cmd57_info()
            res = run_tch_sync()
            if res == TEST_OK:
                run_tx_tests()
                tr.set_test_scope("TRX%d/BER1" % trx)
                run_ber_tests()
finally:
    # switch back to TRX1
    bts.trx_set_primary(1)
    bts.restart_runit_service("osmo-trx")


#
#   Dump report to a JSON file
#

f = file("bts-test.log.json", 'w')
f.write(tr.json())
f.close()
