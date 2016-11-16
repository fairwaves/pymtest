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

from fwtp_core import *
from testsuite_bts import *

# Enable/disable debug mode
_tests_debug = 1

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
    def print_result(self, t, path, ti, result, value, old_result, old_value, delta, reason):
        pass

    def __init__(self):
        self.test_results = {}
        self.prev_test_results = {}
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


    def skip_test(self, path, ti, skip_result=TEST_NA, reason=None):
        t = time.time()
        delta = None
        old_t, old_result, old_value = self._get_old(path, ti)
        if old_t is not None:
            self._get_scope_subtree()[ti.testname] = (old_t, old_result, old_value)
        self.print_result(t, path, ti, skip_result, None, old_result, old_value, delta, reason)


    def _get_old(self, path, ti):
        if (len(self.prev_test_results) == 0 or
          self.scope not in self.prev_test_results or
          ti.testname   not in self.prev_test_results[self.scope]):
            return (None, None, None)
        return self.prev_test_results[self.scope][ti.testname]

    def set_test_result(self, path, ti, result, value=None):
        t = time.time()
        delta = None
        old_t, old_result, old_value = self._get_old(path, ti)
        try:
            fprev = float(old_value)
            fnew = float(value)
            delta = fnew - fprev
        except:
            pass
        self._get_scope_subtree()[ti.testname] = (t, result, value)
        self.print_result(t, path, ti, result, value, old_result, old_value, delta)

        return result

    def check_test_result(self, path, ti, value, **kwargs):
        #res = self.checks[ti.testname](value)
        res = ti.CHECK(value, kwargs)
        self.set_test_result(path, ti, res, value)
        return res

    def get_test_result(self, path, ti, scope=None):
        return self._get_scope_subtree(scope).get(ti.testname, (0, TEST_NA, None))

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

def def_func_visitor(path, ti, *args, **kwargs):
    global ABORT_EXECUTION
    testname = ti.testname
    func = ti.func
    if testname in EXCLUDE_TESTS:
        res = TEST_NA
        #tr.print_result(time.time(), testname, res, None)
        tr.skip_test(path, ti, res)
        return res
    if ABORT_EXECUTION:
        res = TEST_ABORTED
        #tr.set_test_result(testname, res)
        tr.skip_test(path, ti, res)
        return res

    try:
        val = func(*args, **kwargs)
        res = tr.check_test_result(path, ti, val, **kwargs)
    except KeyboardInterrupt:
        res = TEST_ABORTED
        tr.set_test_result(path, ti, res)
        ABORT_EXECUTION=True
    except TimeoutError as e:
        res = TEST_FAIL
        tr.set_test_result(path, ti, res)
        print ("Error: %s" % e)
    except:
        if _tests_debug:
            traceback.print_exc()
        res = TEST_ABORTED
        tr.set_test_result(path, ti, res)
    return res

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
               "umtrx_ctrl.py", "umtrx_lms.py"]

    locals = ["test_umtrx_reset.py", "test_umtrx_gps_time.py"]

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        ''' Connect to a BTS and prepare it for testing '''
        # Copy helper scripts to the BTS
        self.tmpdir = tmpdir
        self._exec_stdout('mkdir -p '+self.tmpdir)
        self._copy_file_list('helper/', self.helpers, self.tmpdir)
        self._copy_file_list('./', self.locals, self.tmpdir)
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
            '%s python3 test_umtrx_gps_time.py' % (self.sudo))

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

    def umtrx_reset_test(self):
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python3 test_umtrx_reset.py' % self.sudo)

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

    def __init__(self, bts_ip, port=22, username='', password='',
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
#   CMD57 control functions
###############################


def cmd57_init(cmd57_port):
    dev = cmd57.rs232(cmd57_port, rtscts=True)
    atexit.register(dev.quit)
    return dev

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
    parser.add_argument("-s", "--script", dest='script', type=str, default=None,
                        help="Run external script")
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

    def __init__(self):
        super().__init__()

    def output_progress(self, string):
            print(string)

    def print_result(self, t, path, ti, result, value, old_result, old_value, delta, reason=None):
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
        exr = "" if reason is None else " (%s)" % reason
        print ("[%s] %s%50s:  %s%7s%s%s%s" % (
            time.strftime("%d %B %Y %H:%M:%S", time.localtime(t)),
            tcolot,
            ti.INFO, #TEST_NAMES.get(testname, testname),
            ConsoleTestResults.RESULT_COLORS[result],
            TEST_RESULT_NAMES[result],
            bcolors.ENDC,
            was,
            exr), end="")
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

def str2bool(v):
    if isinstance(v, bool):
        return v
    return v.lower() in ("yes", "true", "t", "1")

def apply_subs(string, **variables):
    for key, value in variables.items():
        string = string.replace("{{%s}}" % key, str(value))
    return string

def merge_dicts(base, extention, **extra):
    d = { k: base[k] for k in base.keys() }
    for e in extention.keys():
        d[e] = extention[e]
    for x in extra.keys():
        d[x] = extra[x]
    return d

class TestCaseCall:
    def __init__(self, testname, testcallscript = None):
        print("C: %s : %s" % (testname, testcallscript))
        self.enable = True
        self.test = testname
        self.name = testname
        self.desc = testname # TODO
        self.abort_bundle_on_failure = False
        self.args = None #no extra args
        self.errors = 0

        if not testname in TestSuiteConfig.KNOWN_TESTS_DESC:
            print ("Test `%s` hasn't been found nknown tests" % testname)
            self.errors = self.errors + 1

        if testcallscript is not None:
            self.abort_bundle_on_failure = str2bool(testcallscript["abort_bundle_on_failure"]) if "abort_bundle_on_failure" in testcallscript else False
            self.args = testcallscript["args"] if "args" in testcallscript else None

    def __str__(self):
        return self.test

    def run(self, path, **kwargs):
        ti = TestSuiteConfig.KNOWN_TESTS_DESC[self.test]
        if not self.enable:
            kwargs["TR"].output_progress("Test %s in %s bundle is disabled" % (self.test, path))
            return True
        if ti.check_dut(dut):
            print ("Calling %s/%s -> %s()" % (path, self.test, ti.func.__name__))

            res = TestSuiteConfig.DECORATOR_DEFAULT(path, ti, **kwargs)
            if self.abort_bundle_on_failure and res != TEST_OK:
                kwargs["TR"].output_progress("Test %s failed which also fails whole %s bundle" % (self.test, path))
                return False
        else:
            kwargs["TR"].skip_test(path, ti, TEST_NA,
                                  "Function %s in bundle %s isn't compatible with DUT:%s, ignoring" % (ti.func.__name__, self.name, dut))
        return True

class TestRepeat:
    def __init__(self, repeatscript):
        print ("R: %s" % repeatscript)
        self.enable = True
        self.errors = 0
        self.name = repeatscript["name"] if "name" in repeatscript else "<repeat>"
        self.desc = repeatscript["description"] if "description" in repeatscript else self.name
        self.args = repeatscript["args"] if "args" in repeatscript else None
        if self.args is not None:
            self.count = len(self.args)
            self.untill = None
        elif "count" in repeatscript:
            self.count = repeatscript["count"]
            self.untill = None
        else:
            self.errors = self.errors + 1

        if "bundle" in repeatscript:
            self.execute = TestBundle(repeatscript["bundle"])
        elif "repeat" in repeatscript:
            self.execute = TestRepeat(repeatscript["repeat"])
        else:
            self.errors = self.errors + 1
            return
        self.errors += self.execute.errors

    def __str__(self):
        return self.name

    def run(self, path, **kwargs):
        if not self.enable:
            return True
        i = 0
        if self.args is not None:
            for a in self.args:
                ea = { k: apply_subs(a[k], **kwargs) if isinstance(a[k], str) else a[k] for k in a.keys() }
                self.execute.run("%s/%s@%s" % (path, self.name, ea), **merge_dicts(kwargs, ea, ITER="%s/%d" % (kwargs["ITER"],i) ))
                i += 1


class TestBundle:
    def __init__(self, bundlescript):
        print ("B: %s" % bundlescript)
        self.enable = True
        self.name = bundlescript["name"]
        self.desc = bundlescript["description"] if "description" in bundlescript else self.name
        self.scope = bundlescript["scope"] if "scope" in bundlescript else "global"
        self.tests = []
        self.errors = 0
        for test in bundlescript["testsuites"]:
            self.errors = self.errors + self._checktests(test)

    def __str__(self):
        return self.name
    def __repr__(self):
        return "Name: %s, Desc: '%s', tests: '%s'" % (self.name, self.desc, self.tests)

    def _checktests(self, testscript):
        if isinstance(testscript, dict):
            key = next(iter(testscript.keys()))
            if key == "bundle":
                test = TestBundle(testscript[key])
            elif key == "repeat":
                test = TestRepeat(testscript[key])
            else:
                test = TestCaseCall(key, testscript[key])
        else:
            test = TestCaseCall(testscript, None)
        if test.errors == 0:
            self.tests.append(test)
        return test.errors

    def run_bundle(self, **kwargs):
        return self.run("", **merge_dicts(kwargs, {"ITER":""}))

    def run(self, path, **kwargs):
        if not self.enable:
            return True

        scope = apply_subs(self.scope, **kwargs)
        kwargs["TR"].set_test_scope(scope)
        for t in self.tests:
            if not t.run("%s/%s" % (path, self.name), **kwargs):
                # Bundle aborted
                return False
        return True

import yaml
class TestExecutor:
    def __init__(self, testscript):
        self.yamltree = yaml.load(testscript)
        self.bundles = []
        self.errors = 0

        for i in self.yamltree:
            self._initbundle(i)

        if self.errors > 0:
            print ("Got %d errors in testscript, aborting" % self.errors)
            sys.exit(6)

    def _initbundle(self, bundletree):
        if "bundle" in bundletree:
            #try:
                bundle = TestBundle(bundletree["bundle"])
                self.bundles.append(bundle)
                self.errors = self.errors + bundle.errors
            #except:
            #    self.errors = self.errors + 1
            #    print ("Bundle '%s' contains errors" % bundletree["bundle"])
        else:
            self.errors = self.errors + 1
            print ("Parsing error, don't know how to handle: %s" % bundletree)


    def run(self, **kwargs):
        print ("Run testsuite with global variables: `%s`" % kwargs)
        for b in self.bundles:
            kwargs["TR"].output_progress ("Executing bundle: %s" % b)
            b.run_bundle(**kwargs)


def finalize_testsuite(tr):
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

    test_id = str(tr.get_test_result("/", TestSuiteConfig.KNOWN_TESTS_DESC["test_id2"], "system")[2])
    f = open("out/bts-test."+test_id+".json", 'w')
    f.write(tr.json())
    f.close()

##################
#   Main
##################
if __name__ == '__main__':
    TestSuiteConfig.DECORATOR_DEFAULT = def_func_visitor
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
    #tr = ConsoleTestResults(init_test_checks(dut_checks))
    #test_deps = TestDependencies()

    #
    #   BTS tests
    #
    tr = ConsoleTestResults()

    # Establish ssh connection with the BTS under test
    print("Establishing connection with the BTS.")
    if args.bts_ip == "local":
        bts = BtsControlLocal()
    elif args.bts_ip == "manual":
        bts = BtsControlLocalManual()
    else:
        bts = BtsControlSsh(args.bts_ip, 22, dut_checks['login'], dut_checks['password'])

    band = get_band(args.arfcn)
    if args.script is not None:
        texec = TestExecutor(open(args.script, "r").read())

        cmd = cmd57_init(args.cmd57_port)
        texec.run(DUT=dut, DUT_CHECKS=dut_checks, BTS=bts, ARFCN=args.arfcn, TR=tr, BAND=band, CMD=cmd, CHAN='')
        finalize_testsuite(tr)
        sys.exit(0)


    execargs = {'DUT':dut,
                'DUT_CHECKS':dut_checks,
                'BTS':bts,
                'ARFCN':args.arfcn,
                'TR':tr,
                'BAND':band,
                'CHAN':''}

    # CMD57 has sloppy time synchronization, so burst timing can drift
    # by a few symbols
#    bts.bts_set_maxdly(10)
    bts.bts_led_blink(2)

    tr.set_test_scope("system")
    run_bts_tests(execargs)

    if len(args.channels) == 0:
        print("No channel tests were selected")
        bts.osmo_trx_restart()
        bts.bts_led_on()
        sys.exit(0)

    #
    #   CMD57 tests
    #

    # Establish connection with CMD57 and configure it
#    print("Establishing connection with the CMD57.")
#    cmd = cmd57_init(args.cmd57_port)
#    if dut.startswith("UmTRX"):
#        cmd.set_io_used('I1O2')
#    else:
#        cmd.set_io_used('I1O1')

#    set_band_using_arfcn(cmd, args.arfcn)

#    cmd.switch_to_man_bidl()
#    cmd57_configure(cmd, args.arfcn)

    test_configure_cmd57(execargs)

    try:
        channels = args.channels.split(',')
        trxes = [ int(i) for i in channels ]
        for trx in trxes:
            execargs['CHAN'] = trx
            resp = ui_ask("Connect CMD57 to the TRX%d." % trx)
            if resp:
                tr.set_test_scope("TRX%d" % trx)
                tr.output_progress(bts.trx_set_primary(trx))
                bts.osmo_trx_restart()
                run_cmd57_info()
                res = run_tch_sync()
                if res == TEST_OK:
                    run_tx_tests(execargs)
                    ber_scope = "TRX%d/BER" % trx
                    tr.set_test_scope(ber_scope)
                    run_ber_tests(dut)
                    if tr.get_test_result("ber_test_result")[1] != TEST_OK:
                        tr.output_progress("Re-running BER test")
                        tr.clear_test_scope(ber_scope)
                        run_ber_tests(dut)
                    if not dut.startswith("UmTRX"):
                        tr.set_test_scope("TRX%d/power" % trx)
                        test_power_vswr_vga2(execargs)
                        test_power_vswr_dcdc(execargs)
                        resp = ui_ask("Disconnect cable from the TRX%d." % trx)
                        if resp:
                            test_vswr_vga2(execargs)
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


