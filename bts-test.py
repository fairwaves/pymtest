#!/usr/bin/python3
import paramiko
from scpi.devices import cmd57_console as cmd57
from scpi.errors import TimeoutError
import atexit
import argparse
import traceback
import re
import json
import os, sys, select  # for stdin flush
import subprocess
from abc import ABCMeta, abstractmethod

import bts_params

UMSITE_TM3_VGA2_DEF = 22
UMTRX_VGA2_DEF = UMSITE_TM3_VGA2_DEF

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


def test_substr_checker(okstr):
    return lambda val: TEST_OK if okstr.find(val) != -1 \
                               else TEST_FAIL

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
    "test_id": "Test ID",
    "bts_uname": "BTS system information",
    "bts_hw_model": "BTS hardware model",
    "bts_hw_band": "BTS hardware band",
    "bts_umtrx_ver": "BTS umtrx ver",
    "bts_network_cards": "BTS network cards PCI IDs",
    "umtrx_gps_time": "UmTRX GPS time",
    "umtrx_gpsdo_wait": "Waiting for UmTRX GPSDO to stabilize frequency",
    "umtrx_serial": "UmTRX serial number",
    "umtrx_autocalibrate": "UmTRX autocalibration",
    "umtrx_reset_test" : "UmTRX Reset and Safe firmware loading test",
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
    "ber_configure": "BER test configuration",
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

def init_test_checks(DUT_PARAMS):
    return {
        "test_id": test_none_checker(),
        "bts_uname": test_ignore_checker(),
        "bts_hw_model": test_substr_checker(
            DUT_PARAMS["hw_model"]),
        "bts_hw_band": test_ignore_checker(),
        "bts_umtrx_ver": test_val_checker('2.3.1'),
        "bts_network_cards": test_val_checker('pci0 10ec:8168, pci1 8086:1533'),
        "umtrx_serial": test_none_checker(),
        "umtrx_autocalibrate": test_bool_checker(),
        "umtrx_reset_test": test_bool_checker(),
        "umtrx_gps_time": test_bool_checker(),
        "umtrx_gpsdo_wait": test_bool_checker(),
        "tester_name": test_ignore_checker(),
        "tester_serial": test_ignore_checker(),
        "tester_version": test_ignore_checker(),
        "tester_options": test_ignore_checker(),
        "bcch_presence": test_bool_checker(),
        "burst_power_peak": test_minmax_checker(
            DUT_PARAMS["burst_power_peak_min"],
            DUT_PARAMS["burst_power_peak_max"]),
        "burst_power_avg": test_minmax_checker(
            DUT_PARAMS["burst_power_avg_min"],
            DUT_PARAMS["burst_power_avg_max"]),
        "burst_power_array": test_ignore_checker(),
        "freq_error": test_minmax_checker(
            -DUT_PARAMS["freq_error"],
            DUT_PARAMS["freq_error"]),
        "phase_err_array": test_ignore_checker(),
        "phase_err_pk": test_minmax_checker(
            DUT_PARAMS["phase_err_pk_min"],
            DUT_PARAMS["phase_err_pk_max"]),
        "phase_err_avg": test_minmax_checker(
            DUT_PARAMS["phase_err_avg_min"],
            DUT_PARAMS["phase_err_avg_max"]),
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
        "ber_configure": test_ignore_checker(),
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

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class TestResults(metaclass=ABCMeta):
    @abstractmethod
    def output_progress(self, string):
        pass

    @abstractmethod
    def print_result(self, t, testname, result, value, old_result, old_value, delta):
        pass

    def __init__(self, checks):
        self.test_results = {}
        self.prev_test_results = {}
        self.checks = checks
        self.scope = 'global'

    def load_prev_data(self, test_id):
        best_file = None
        best_i = -1
        check_string = "bts-test.%s_" % test_id
        for file in os.listdir("out/"):
            i = file.startswith(check_string)
            if i > 0:
                 self.output_progress("JSON data found on %s" % file[i+len(check_string)-1:-5])
                 ddx = [int(x) for x in file[i+len(check_string)-1:-5].split('-')]
                 idx = ((100 * ddx[0] + ddx[1]) * 100 + ddx[2]) * 1000000 + ddx[3]
                 if idx > best_i:
                     best_i = idx
                     best_file = file
        if best_i == -1:
            self.output_progress('No previous data were found for %s' % test_id)
            return

        self.output_progress('Loading previous data from %s' % best_file)
        with open("out/" + best_file, 'rt', encoding="utf-8") as content:
            self.prev_test_results = json.loads(content.read())
            for scopename in self.prev_test_results:
                curr_scope = self._get_scope_subtree(scopename)
                for testname in self.prev_test_results[scopename]:
                    if testname not in curr_scope:
                        curr_scope[testname] = self.prev_test_results[scopename][testname]


    def set_test_scope(self, scope):
        self.scope = scope

    def clear_test_scope(self, scope):
        if scope in self.test_results:
            self.test_results[scope] = {}

    def _get_scope_subtree(self, scope=None):
        if scope is None:
            scope = self.scope
        return self.test_results.setdefault(scope, {})


    def skip_test(self, testname, skip_result=TEST_NA):
        t = time.time()
        delta = None
        old_t, old_result, old_value = self._get_old(testname)
        if old_t is not None:
            self._get_scope_subtree()[testname] = (old_t, old_result, old_value)
        self.print_result(t, testname, skip_result, None, old_result, old_value, delta)


    def _get_old(self, testname):
        if (len(self.prev_test_results) == 0 or
          self.scope not in self.prev_test_results or
          testname   not in self.prev_test_results[self.scope]):
            return (None, None, None)
        return self.prev_test_results[self.scope][testname]

    def set_test_result(self, testname, result, value=None):
        t = time.time()
        delta = None
        old_t, old_result, old_value = self._get_old(testname)
        try:
            fprev = float(old_value)
            fnew = float(value)
            delta = fnew - fprev
        except:
            pass
        self._get_scope_subtree()[testname] = (t, result, value)
        self.print_result(t, testname, result, value, old_result, old_value, delta)

        return result

    def check_test_result(self, testname, value):
        res = self.checks[testname](value)
        self.set_test_result(testname, res, value)
        return res

    def get_test_result(self, testname, scope=None):
        return self._get_scope_subtree(scope).get(testname, (0, TEST_NA, None))

    def json(self):
        return json.dumps(self.test_results,
                          indent=4, separators=(',', ': '))

    def summary(self):
        stat={}
        for scopename in self.test_results:
            for testname in self.test_results[scopename].keys():
                tres = self.test_results[scopename][testname]
                if tres is not None:
                    cnt = stat.setdefault(tres[1], 0)
                    stat[tres[1]] = cnt + 1
        return stat

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
EXCLUDE_TESTS=[]
ABORT_EXECUTION = False

def def_func_visitor(func, testname, *args, **kwargs):
    global ABORT_EXECUTION
    if testname in EXCLUDE_TESTS:
        res = TEST_NA
        #tr.print_result(time.time(), testname, res, None)
        tr.skip_test(testname, res)
        return res
    if ABORT_EXECUTION:
        res = TEST_ABORTED
        #tr.set_test_result(testname, res)
        tr.skip_test(testname, res)
        return res

    try:
        val = func(*args, **kwargs)
        res = tr.check_test_result(testname, val)
    except KeyboardInterrupt:
        res = TEST_ABORTED
        tr.set_test_result(testname, res)
        ABORT_EXECUTION=True
    except TimeoutError as e:
        res = TEST_FAIL
        tr.set_test_result(testname, res)
        print ("Error: %s" % e)
    except:
        if _tests_debug:
            traceback.print_exc()
        res = TEST_ABORTED
        tr.set_test_result(testname, res)
    return res

DECORATOR_DEFAULT = def_func_visitor

def test_checker_decorator(testname):
    def real_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return DECORATOR_DEFAULT(func, testname, *args, **kwargs)
        return wrapper
    return real_decorator

###############################
#   BTS control functions
###############################

class BtsControlBase:

    helpers = ["obscvty.py", "osmobts-en-loopback.py",
               "osmobts-set-maxdly.py", "osmobts-set-slotmask.py",
               "osmo-trx-primary-trx.py", "umtrx_set_dcdc_r.py",
               "umtrx_get_vswr_sensors.py",
               # TODO: Move this from helpers to packages
               "umtrx_property_tree.py",
               "umtrx_ctrl.py", "umtrx_lms.py",
               "umtrx_reset_test.py", "umtrx_gps_time_test.py",
               "umtrx_wait_stable_gpsdo.py"]

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        ''' Connect to a BTS and prepare it for testing '''
        # Copy helper scripts to the BTS
        self.tmpdir = tmpdir
        self._exec_stdout('mkdir -p '+self.tmpdir)
        self._copy_file_list('helper/', self.helpers, self.tmpdir)
        self.sudo = sudopkg

    def _tee(self, stream, filename):
        ''' Write lines from the stream to the file and return the lines '''
        lines = [  i if type(i) is str else i.decode("utf-8")  for i in stream.readlines() ]
        f = open(filename, 'w')
        f.writelines(lines)
        f.close()
        return lines

    def get_uname(self):
        ''' Get uname string '''
        return self._exec_stdout('uname -a')[0].strip()

    def trx_set_primary(self, num):
        ''' Set primary TRX '''
        print ("Setting primary TRX to TRX%d" % num)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python osmo-trx-primary-trx.py %d' % (self.sudo, num))

    def bts_en_loopback(self):
        ''' Enable loopbak in the BTS '''
        print ("Enabling BTS loopback")
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-en-loopback.py')

    def bts_set_slotmask(self, ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7):
        ''' Set BTS TRX0 slotmask '''
        print ("Setting BTS slotmask")
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-slotmask.py %d %d %d %d %d %d %d %d'
            % (ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7))

    def umtrx_get_gps_time(self):
        '''Obtain time diff GPS vs system'''
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python umtrx_gps_time_test.py' % (self.sudo))

    def umtrx_wait_gpsdo(self):
        '''Wait for GPSDO to stabilize'''
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python umtrx_wait_stable_gpsdo.py' % (self.sudo))

    def bts_get_hw_config(self, param):
        ''' Get hardware configuration parameter '''
        return self._exec_stdout_stderr(
             'cat /etc/osmocom/hardware.conf | grep %s | cut -d= -f2' % param)

    def bts_set_maxdly(self, val):
        ''' Set BTS TRX0 max timing advance '''
        print("BTS: setting max delay to %d." % val)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-maxdly.py %d' % val)

    def bts_led_blink(self, period=1):
        ''' Continously blink LED '''
        return self._exec_stdout_stderr(
             '%s umsite-led-blink_%dhz.sh' % (self.sudo, period))

    def bts_led_on(self, on=1):
        ''' On or off system LED'''
        return self._exec_stdout_stderr(
             '%s umsite-led-on-%s.sh' % ( self.sudo, 'on' if on else 'off'))

    def bts_shutdown(self):
        ''' Shutdown BTS host '''
        return self._exec_stdout_stderr(
            '%s shutdown -h now' % (self.sudo))

    def bts_get_pci_ids(self):
        ''' Check that we have correct network cards installed. '''
        stdin, stdout, stderr = self._exec(
            'lspci -n')
        pci1_re = re.compile(r'^01:00.0 [\da-z]+: ([\da-z:]+)')
        pci2_re = re.compile(r'^02:00.0 [\da-z]+: ([\da-z:]+)')

        interfaces = []
        for l in stdout:
            match = pci1_re.match(l)
            if match is not None:
                interfaces.append('pci0 '+match.group(1))
                continue
            match = pci2_re.match(l)
            if match is not None:
                interfaces.append('pci1 '+match.group(1))
        return interfaces

    def umtrx_reset_test(self):
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python3 umtrx_reset_test.py' % self.sudo)

    def umtrx_set_dcdc_r(self, val):
        ''' Set UmTRX DCDC control register value '''
#        print("UmTRX: setting DCDC control register to %d." % val)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_set_dcdc_r.py %d' % val)

    def umtrx_set_tx_vga2(self, chan, val):
        ''' Set UmTRX Tx VGA2 gain '''
#        print("UmTRX: setting UmTRX Tx VGA2 gain for chan %d to %d."
#              % (chan, val))
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_lms.py --lms %d --lms-set-tx-vga2-gain %d'
            % (chan, val))

    def umtrx_get_vswr_sensors(self, chan):
        ''' Read UmTRX VPR and VPF sensors '''
        lines = self._exec_stdout(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_get_vswr_sensors.py')
        res = [float(x.strip()) for x in lines]
        start = (chan-1)*2
        return res[start:start+2]

    def start_runit_service(self, service):
        ''' Start a runit controlled service '''
        print("Starting '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv start %s' % (self.sudo, service))
        # TODO: Check result

    def stop_runit_service(self, service):
        ''' Stop a runit controlled service '''
        print("Stopping '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv stop %s' % (self.sudo, service))
        # TODO: Check result

    def restart_runit_service(self, service):
        ''' Restart a runit controlled service '''
        print("Restarting '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv restart %s' % (self.sudo, service))
        # TODO: Check result

    def osmo_trx_start(self):
        return self.start_runit_service("osmo-trx")

    def osmo_trx_stop(self):
        return self.stop_runit_service("osmo-trx")

    def osmo_trx_restart(self):
        return self.restart_runit_service("osmo-trx")

    def get_umtrx_eeprom_val(self, name):
        ''' Read UmTRX serial from EEPROM.
            All UHD apps should be stopped at the time of reading. '''
        lines = self._exec_stdout_stderr(
            '/usr/lib/uhd/utils/usrp_burn_mb_eeprom --values "serial"')
        eeprom_val = re.compile(r'    EEPROM \["'+name+r'"\] is "(.*)"')
        for s in lines:
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
        stdin, stdout, stderr = self._exec(
            '%s umtrx_auto_calibration %s' % (self.sudo, preset))
        # TODO: Check result
        lines = self._tee(stdout, filename_stdout)
        self._tee(stderr, filename_stderr)
        line_re = re.compile(r'Calibration type .* side . from .* to .*: ([A-Z]+)')
        if len(lines) == 0:
            return False

        for l in lines:
            match = line_re.match(l)
            if match is not None:
                if match.group(1) != 'SUCCESS':
                    return False
        return True

    def _exec_stdout(self, cmd_str):
        barrs = self._exec_stdout_b(cmd_str)
        print (barrs)
        return [ i if type(i) is str else i.decode("utf-8") for i in barrs ]

    def _exec_stdout_stderr(self, cmd_str):
        barrs = self._exec_stdout_stderr_b(cmd_str)
        print (barrs)
        return [ i if type(i) is str else i.decode("utf-8") for i in barrs ]

class BtsControlSsh(BtsControlBase):

    def __init__(self, bts_ip, port=22, username='fairwaves', password='fairwaves',
                 tmpdir='/tmp/bts-test'):
        ''' Connect to a BTS and prepare it for testing '''
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(bts_ip, port=port, username=username, password=password, timeout=2)
        BtsControlBase.__init__(self, tmpdir)

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        sftp = self.ssh.open_sftp()
        for f in flie_list:
            sftp.put(dir_from+f, dir_to+'/'+f)
        sftp.close()

    def _exec(self, cmd_str):
        return self.ssh.exec_command(cmd_str)

    def _exec_stdout(self, cmd_str):
        stdin, stdout, stderr = self.ssh.exec_command(cmd_str)
        return stdout.readlines()

    def _exec_stdout_stderr(self, cmd_str):
        stdin, stdout, stderr = self.ssh.exec_command(cmd_str)
        return stderr.readlines() + stdout.readlines()


class BtsControlLocalManual(BtsControlBase):

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        ''' Connect to a BTS and prepare it for testing '''
        BtsControlBase.__init__(self, tmpdir, sudopkg)

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        for f in flie_list:
            subprocess.check_call(["cp", dir_from+f, dir_to+'/'+f])

    def _exec(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        return (p.stdin, p.stdout, p.stderr)

    def _exec_stdout_b(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdout=subprocess.PIPE,
                             shell=True)
        return p.stdout.readlines()

    def _exec_stdout_stderr_b(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             shell=True)
        return p.stdout.readlines()

    def osmo_trx_start(self):
        return ui_ask("Please start osmo-trx")

    def osmo_trx_stop(self):
        return ui_ask("Please stop osmo-trx")

    def osmo_trx_restart(self):
        return ui_ask("Please restart osmo-trx")


class BtsControlLocal(BtsControlBase):

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        ''' Connect to a BTS and prepare it for testing '''
        BtsControlBase.__init__(self, tmpdir, sudopkg)

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        for f in flie_list:
            subprocess.check_call(["cp", dir_from+f, dir_to+'/'+f])

    def _exec(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        return (p.stdin, p.stdout, p.stderr)

    def _exec_stdout_b(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdout=subprocess.PIPE,
                             shell=True)
        return p.stdout.readlines()

    def _exec_stdout_stderr_b(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             shell=True)
        return p.stdout.readlines()

    def osmo_trx_start(self):
        return self._exec_stdout_stderr("%s sv start osmo-trx" % self.sudo)

    def osmo_trx_stop(self):
        return self._exec_stdout_stderr("%s sv stop osmo-trx" % self.sudo)

    def osmo_trx_restart(self):
        return self._exec_stdout_stderr("%s sv restart osmo-trx" % self.sudo)


###############################
#   non-CMD57 based tests
###############################

@test_checker_decorator("bts_hw_model")
def bts_hw_model(bts):
    return bts.bts_get_hw_config('HW_MODEL')[0].strip('\n')

@test_checker_decorator("bts_hw_band")
def bts_hw_band(bts):
    return bts.bts_get_hw_config('BAND')[0].strip('\n')

@test_checker_decorator("bts_umtrx_ver")
def bts_umtrx_ver(bts):
    return bts.bts_get_hw_config('UMTRX_VER')[0].strip('\n')

@test_checker_decorator("umtrx_reset_test")
def umtrx_reset_test(bts, tr):
    lns = bts.umtrx_reset_test()
    tr.output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1

@test_checker_decorator("umtrx_gps_time")
def umtrx_gps_time(bts, tr):
    lns = bts.umtrx_get_gps_time()
    tr.output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1

@test_checker_decorator("bts_network_cards")
def bts_network_cards(bts):
    interfaces = bts.bts_get_pci_ids()
    return ', '.join(interfaces)

@test_checker_decorator("umtrx_gpsdo_wait")
def umtrx_gpsdo_wait(bts, tr):
    lns = bts.umtrx_wait_gpsdo()
    tr.output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1


@test_checker_decorator("bts_uname")
def bts_read_uname(bts):
    return bts.get_uname()


@test_checker_decorator("umtrx_serial")
def bts_read_umtrx_serial(bts):
    return bts.get_umtrx_eeprom_val("serial")


@test_checker_decorator("test_id")
def gen_test_id():
    ''' Generates a unique test ID '''
    uname_res = tr.get_test_result("bts_uname", "system")
    serial_res =  tr.get_test_result("umtrx_serial", "system")
    if uname_res[1] != TEST_OK or serial_res[1] != TEST_OK:
        return None
    name = uname_res[2].split()[1]
    timestr = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(time.time()))
    fixed_test_id = name+'_'+serial_res[2]
    tr.load_prev_data(fixed_test_id)
    return fixed_test_id+'_'+timestr


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
    cmd.set_phase_decoding_mode('GATBits')
    print ("ARFCN=%d NET=%s" % (cmd.ask_bts_ccch_arfcn(), cmd.ask_network_type()))

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
        if res == TEST_ABORTED:
            return res
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


@test_checker_decorator("ber_configure")
def test_ber_configure(cmd, dut):
    if dut == "UmTRX":
        cmd.set_ber_test_num(3)
        return cmd.set_ber_used_ts_power(-75)
    else:
        return cmd.set_ber_test_num(1)


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
def test_power_vswr_vga2(cmd, bts, chan, tr):
    try:
        tr.output_progress ("Testing power&VSWR vs VGA2")
        tr.output_progress ("VGA2\tPk power\tAvg power\tVPF\tVPR")
        res = []
        for vga2 in range(26):
            bts.umtrx_set_tx_vga2(chan, vga2)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, power_pk, power_avg, vpf, vpr))
            tr.output_progress("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for vga2 in range(25, -1, -1):
            bts.umtrx_set_tx_vga2(chan, vga2)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, power_pk, power_avg, vpf, vpr))
            tr.output_progress("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_tx_vga2(chan, UMTRX_VGA2_DEF)


@test_checker_decorator("vswr_vga2")
def test_vswr_vga2(bts, chan, tr):
    try:
        tr.output_progress ("Testing VSWR vs VGA2")
        tr.output_progress ("VGA2\tVPF\tVPR")
        res = []
        for vga2 in range(26):
            bts.umtrx_set_tx_vga2(chan, vga2)
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, vpf, vpr))
            tr.output_progress("%d\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for vga2 in range(25, -1, -1):
            bts.umtrx_set_tx_vga2(chan, vga2)
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((vga2, vpf, vpr))
            tr.output_progress("%d\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_tx_vga2(chan, UMTRX_VGA2_DEF)


@test_checker_decorator("power_vswr_dcdc")
def test_power_vswr_dcdc(cmd, bts, chan, tr, dut):
    try:
        tr.output_progress ("Testing power&VSWR vs DCDC control")
        tr.output_progress ("DCDC_R\tPk power\tAvg power\tVPF\tVPR")
        res = []
        for dcdc in range(dut["ddc_r_min"], dut["ddc_r_max"]+1):
            bts.umtrx_set_dcdc_r(dcdc)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((dcdc, power_pk, power_avg, vpf, vpr))
            tr.output_progress("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for dcdc in range(dut["ddc_r_max"], dut["ddc_r_min"]-1, -1):
            bts.umtrx_set_dcdc_r(dcdc)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((dcdc, power_pk, power_avg, vpf, vpr))
            tr.output_progress("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        return res
    finally:
        bts.umtrx_set_dcdc_r(dut["ddc_r_def"])


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


def run_bts_tests(tr, band):
    print("Starting BTS tests.")

    # Stop osmo-trx to unlock UmTRX
    bts.osmo_trx_stop()

    # Collect information about the BTS
    bts_read_uname(bts)
    bts_read_umtrx_serial(bts)

    umtrx_gps_time(bts, tr)
    bts_hw_model(bts)
    bts_hw_band(bts)
    bts_umtrx_ver(bts)
    bts_network_cards(bts)

    # Generate Test ID to be used in file names
    gen_test_id()

    # UmTRX Reset Test
    umtrx_reset_test(bts, tr)

    # Wait for GPSDO to stabilize frequency after reset
    umtrx_gpsdo_wait(bts, tr)

    # Autocalibrate UmTRX
    test_id = str(tr.get_test_result("test_id", "system")[2])
    bts_umtrx_autocalibrate(bts, band, "out/calibration."+test_id+".log", "out/calibration.err."+test_id+".log")

    # Start osmo-trx again
    bts.osmo_trx_start()


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

    # Make sure GPSDO has done stabilizing frequency
    umtrx_gpsdo_wait(bts, tr)

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


def run_ber_tests(dut):
    print("Starting BER tests.")

    test_ber_configure(cmd, dut)

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
    parser.add_argument("-d", "--dut",
                        dest='dut', type=str,
                        help="Device under test for the CMD57 control ")
    parser.add_argument("-x", "--exclude", type=str,
                        help="Exclude some tests")
    parser.add_argument("-L", "--list", type=str,
                        help="Display all available tests and exit")
    parser.add_argument("-c", "--channels", type=str, default='1,2',
                        help="Test only this channels")
    return parser.parse_args()


##################
#   UI functions
##################

class ConsoleTestResults(TestResults):
    RESULT_COLORS = {
            TEST_NA      : bcolors.OKBLUE,
            TEST_ABORTED : bcolors.WARNING,
            TEST_OK      : bcolors.OKGREEN,
            TEST_FAIL    : bcolors.FAIL
        }

    def __init__(self, checks):
        super().__init__(checks)

    def output_progress(self, string):
            print(string)

    def print_result(self, t, testname, result, value, old_result, old_value, delta):
        sdelta = " [%+f]" % delta if delta is not None else ""
        was=" (%7s)%s" % (TEST_RESULT_NAMES[old_result], sdelta) if old_result is not None else ""
        if old_result == result or old_result is None:
            tcolot = bcolors.BOLD
        elif old_result != TEST_OK and result == TEST_OK:
            tcolot = bcolors.OKGREEN
        elif old_result == TEST_OK and result != TEST_OK:
            tcolot = bcolors.FAIL
        else:
            tcolot = bcolors.WARNING

        print ("[%s] %s%50s:  %s%7s%s%s" % (
            time.strftime("%d %B %Y %H:%M:%S", time.localtime(t)),
            tcolot,
            TEST_NAMES.get(testname, testname),
            ConsoleTestResults.RESULT_COLORS[result],
            TEST_RESULT_NAMES[result],
            bcolors.ENDC,
            was), end="")
        if value is not None:
            print (" (%s)" % str(value))
        else:
            print ("")


def ui_ask(text):
    if ABORT_EXECUTION:
         print ("Abort ui '%s'" % text)
         return False

    # Note: this flush code works under *nix OS only
    try:
        while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0])>0:
            os.read(sys.stdin.fileno(), 4096)

        print (" ")
        print ("~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        val = input(text+" ")
        print ("~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print (" ")
        return val != 's' and val != 'c'
    except:
        return False


def get_band(arfcn):
    if arfcn > 511 and arfcn < 886:
        return "DCS1800"
    elif (arfcn > 974 and arfcn < 1024) or arfcn == 0:
        return "EGSM900"
    elif arfcn > 0 and arfcn < 125:
        return "GSM900"
    return None

def set_band_using_arfcn(cmd, arfcn):
    bstr = get_band(arfcn)
    if bstr == "DCS1800":
        cmd.switch_to_idle()
        cmd.set_network_type("DCS1800")
    elif bstr == "EGSM900" or bstr == "GSM900":
        cmd.switch_to_idle()
        cmd.set_network_type("GSM900")
    else:
        print ("This band isn't supported by CMD57")

def check_arfcn(n, band):
    if band == "GSM900":
        return n >= 1 and n <= 124
    elif band == "EGSM900":
        return n >= 0 and n <= 124 or n >= 975 and n <= 1023
    elif band == "RGSM900":
        return n >= 0 and n <= 124 or n >= 955 and n <= 1023
    elif band == "GSM1800" or band == "DCS1800":
        return n >= 512 and n <= 885
    else:
        return False

##################
#   Main
##################
if __name__ == '__main__':
    #
    #   Initialization
    #

    # Parse command line arguments
    args = parse_args()
    dut=args.dut

    if args.exclude is not None:
        EXCLUDE_TESTS = args.exclude.split(',')
        print ("Exclude list: %s" % str(EXCLUDE_TESTS))

    if args.list:
        for i,v in enumerate(TEST_NAMES):
            print("%20s: %50s" % (i, v))

    if dut not in bts_params.HARDWARE_LIST.keys():
        print ("Unknown device %s!\nSupported: %s" % (dut,
                 str([i for i in bts_params.HARDWARE_LIST.keys()])))
        sys.exit(4)

    dut_checks = bts_params.HARDWARE_LIST[dut]

    if dut_checks["hw_band"] is not None and not check_arfcn(args.arfcn, dut_checks["hw_band"]):
        print ("Hardware %s doesn't support ARFCN %d in band %s" % (
                    dut, args.arfcn, dut_checks["hw_band"]))
        sys.exit(5)

    # Initialize test results structure
    tr = ConsoleTestResults(init_test_checks(dut_checks))
    #test_deps = TestDependencies()

    #
    #   BTS tests
    #

    # Establish ssh connection with the BTS under test
    print("Establishing connection with the BTS.")
    if args.bts_ip == "local":
        bts = BtsControlLocal()
    elif args.bts_ip == "manual":
        bts = BtsControlLocalManual()
    else:
        bts = BtsControlSsh(args.bts_ip, 22, 'fairwaves', 'fairwaves')

    # CMD57 has sloppy time synchronization, so burst timing can drift
    # by a few symbols
    bts.bts_set_maxdly(10)
    bts.bts_led_blink(2)

    tr.set_test_scope("system")
    run_bts_tests(tr, get_band(args.arfcn))

    if len(args.channels) == 0:
        print("No channel tests were selected")
        bts.osmo_trx_restart()
        bts.bts_led_on()
        sys.exit(0)

    #
    #   CMD57 tests
    #

    # Establish connection with CMD57 and configure it
    print("Establishing connection with the CMD57.")
    cmd = cmd57_init(args.cmd57_port)
    if dut.startswith("UmTRX"):
        cmd.set_io_used('I1O2')
    else:
        cmd.set_io_used('I1O1')

    set_band_using_arfcn(cmd, args.arfcn)

    cmd.switch_to_man_bidl()
    cmd57_configure(cmd, args.arfcn)

    try:
        channels = args.channels.split(',')
        trxes = [ int(i) for i in channels ]
        for trx in trxes:
            resp = ui_ask("Connect CMD57 to the TRX%d." % trx)
            if resp:
                tr.set_test_scope("TRX%d" % trx)
                tr.output_progress(bts.trx_set_primary(trx))
                bts.osmo_trx_restart()
                run_cmd57_info()
                res = run_tch_sync()
                if res == TEST_OK:
                    run_tx_tests()
                    ber_scope = "TRX%d/BER" % trx
                    tr.set_test_scope(ber_scope)
                    run_ber_tests(dut)
                    if tr.get_test_result("ber_test_result")[1] != TEST_OK:
                        tr.output_progress("Re-running BER test")
                        tr.clear_test_scope(ber_scope)
                        run_ber_tests(dut)
                    if not dut.startswith("UmTRX"):
                        tr.set_test_scope("TRX%d/power" % trx)
                        test_power_vswr_vga2(cmd, bts, trx, tr)
                        test_power_vswr_dcdc(cmd, bts, trx, tr, dut_checks)
                        resp = ui_ask("Disconnect cable from the TRX%d." % trx)
                        if resp:
                            test_vswr_vga2(bts, trx, tr)
    finally:
        # switch back to TRX1
        bts.trx_set_primary(1)
        bts.osmo_trx_restart()
        bts.bts_led_on()

        sm = tr.summary()
        for res in sm:
            print("%s%8s%s: %2d" % (ConsoleTestResults.RESULT_COLORS[res],
                                    TEST_RESULT_NAMES[res],
                                    bcolors.ENDC,
                                    sm[res]))

        failed = sm.setdefault(TEST_NA, 0) + sm.setdefault(TEST_ABORTED, 0) + sm.setdefault(TEST_FAIL, 0)
        if failed > 0:
            print("\n%sWARNING! NOT ALL TEST PASSED!%s\n" % (
                  ConsoleTestResults.RESULT_COLORS[TEST_FAIL], bcolors.ENDC))
        #
        #   Dump report to a JSON file
        #
        if ABORT_EXECUTION:
            print ("Test was aborted, don't save data")
            sys.exit(1)

        test_id = str(tr.get_test_result("test_id", "system")[2])
        f = open("out/bts-test."+test_id+".json", 'w')
        f.write(tr.json())
        f.close()


