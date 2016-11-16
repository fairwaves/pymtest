#!/usr/bin/python3
#import paramiko
import argparse
import traceback
import re
import json
import os, sys, select  # for stdin flush
#import subprocess
from abc import ABCMeta, abstractmethod

import bts_params


#######################
#   Tests definition
#######################
from functools import wraps
import time

from fwtp_core import *
from testsuite_bts import *

import yaml

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

def def_func_visitor(path, ti, kwargs):
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
        val = func(kwargs)
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

class ConsoleUI:
    def ask(text):
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



def str2bool(v):
    if isinstance(v, bool):
        return v
    return v.lower() in ("yes", "true", "t", "1")

def apply_subs(string, variables):
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

    def run(self, path, kwargs):
        ti = TestSuiteConfig.KNOWN_TESTS_DESC[self.test]
        if not self.enable:
            kwargs["TR"].output_progress("Test %s in %s bundle is disabled" % (self.test, path))
            return True
        if ti.check_dut(dut):
            print ("Calling %s/%s -> %s()" % (path, self.test, ti.func.__name__))

            res = TestSuiteConfig.DECORATOR_DEFAULT(path, ti, kwargs)
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

    def run(self, path, kwargs):
        if not self.enable:
            return True
        i = 0
        if self.args is not None:
            for a in self.args:
                ea = { k: apply_subs(a[k], kwargs) if isinstance(a[k], str) else a[k] for k in a.keys() }
                self.execute.run("%s/%s@%s" % (path, self.name, ea), merge_dicts(kwargs, ea, ITER="%s/%d" % (kwargs["ITER"],i) ))
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

    def run(self, path, kwargs):
        if not self.enable:
            return True

        scope = apply_subs(self.scope, kwargs)
        kwargs["TR"].set_test_scope(scope)
        for t in self.tests:
            if not t.run("%s/%s" % (path, self.name), kwargs):
                # Bundle aborted
                return False
        return True


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


    def run(self, args):
        print ("Run testsuite with global variables: `%s`" % args)
        args["ITER"] = ""
        for b in self.bundles:
            args["TR"].output_progress ("Executing bundle: %s" % b)
            b.run("", args)


def finalize_testsuite(args):
    tr = args["TR"]
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

    test_id = args["TEST_ID"]
    #test_id = str(tr.get_test_result("/", TestSuiteConfig.KNOWN_TESTS_DESC["test_id2"], "system")[2])
    f = open("out/bts-test."+test_id+".json", 'w')
    f.write(tr.json())
    f.close()

##################
#   Main
##################
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


    tr = ConsoleTestResults()
    band = get_band(args.arfcn)

    if args.script is not None:
        texec = TestExecutor(open(args.script, "r").read())
        args = {
            "BTS_IP" : args.bts_ip,
            "DUT"    : dut,
            "DUT_CHECKS" : dut_checks,
            "ARFCN"  : args.arfcn,
            "TR"     : tr,
            "UI"     : ConsoleUI(),
            "CHAN"   : "" }
        texec.run(args)
        finalize_testsuite(args)
        sys.exit(0)



