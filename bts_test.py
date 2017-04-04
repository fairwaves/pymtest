#!/usr/bin/python3
import argparse
import traceback
import sys
import select

from fwtp_engine import *

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


EXCLUDE_TESTS = []
ABORT_EXECUTION = False


def def_func_visitor(path, ti, kwargs):
    global ABORT_EXECUTION
    tr = kwargs["TR"]
    testname = ti.testname
    func = ti.func
    if testname in EXCLUDE_TESTS:
        res = TEST_NA
        # tr.print_result(time.time(), testname, res, None)
        tr.skip_test(path, ti, res)
        return res
    if ABORT_EXECUTION:
        res = TEST_ABORTED
        # tr.set_test_result(testname, res)
        tr.skip_test(path, ti, res)
        return res

    try:
        val = func(kwargs)
        res = tr.check_test_result(path, ti, val, **kwargs)
    except KeyboardInterrupt:
        res = TEST_ABORTED
        tr.set_test_result(path, ti, res)
        ABORT_EXECUTION = True
    except TimeoutError as e:
        res = TEST_FAIL
        tr.set_test_result(path, ti, res)
        print("Error: %s" % e)
    except:
        if _tests_debug:
            traceback.print_exc()
        res = TEST_ABORTED
        tr.set_test_result(path, ti, res)
    return res


class ConsoleTestResults(TestResults):
    RESULT_COLORS = {
        TEST_NA: bcolors.OKBLUE,
        TEST_ABORTED: bcolors.WARNING,
        TEST_OK: bcolors.OKGREEN,
        TEST_FAIL: bcolors.FAIL
    }

    def __init__(self):
        super().__init__()

    def output_progress(self, string):
        print(string)

    def enter_bundle(self, t, path, bundle, disc):
        print("[%s] Bundle %s%50s:  %s%s" % (
            time.strftime("%d %B %Y %H:%M:%S", time.localtime(t)),
            bcolors.OKBLUE,
            "%s/%s" % (path, bundle),
            disc,
            bcolors.ENDC))

    def print_result(self, t, path, ti, result, value, old_result,
                     old_value, delta, reason=None):
        sdelta = " [%+f]" % delta if delta is not None else ""
        was = " (%7s)%s" % (TEST_RESULT_NAMES[old_result], sdelta) if \
            old_result is not None else ""
        if old_result == result or old_result is None:
            tcolot = bcolors.BOLD
        elif old_result != TEST_OK and result == TEST_OK:
            tcolot = bcolors.OKGREEN
        elif old_result == TEST_OK and result != TEST_OK:
            tcolot = bcolors.FAIL
        else:
            tcolot = bcolors.WARNING
        exr = "" if reason is None else " (%s)" % reason
        print("[%s] %s%50s:  %s%7s%s%s%s" % (
            time.strftime("%d %B %Y %H:%M:%S", time.localtime(t)),
            tcolot,
            ti.INFO,  # TEST_NAMES.get(testname, testname),
            ConsoleTestResults.RESULT_COLORS[result],
            TEST_RESULT_NAMES[result],
            bcolors.ENDC,
            was,
            exr), end="")
        if value is not None:
            print(" (%s)" % str(value))
        else:
            print("")


class ConsoleUI:
    def ask(self, text):
        global ABORT_EXECUTION
        if ABORT_EXECUTION:
            print("Abort ui '%s'" % text)
            return False

        # Note: this flush code works under *nix OS only
        try:
            while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0]) > 0:
                os.read(sys.stdin.fileno(), 4096)

            print(" ")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            val = input(text + " ")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print(" ")
            return val != 's' and val != 'c'
        except:
            return False


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
    parser.add_argument("-s", "--script", dest='script',
                        type=str, default=None,
                        help="Run external script")
    parser.add_argument("-t", "--trace", dest='trace',
                        type=bool, default=False,
                        help="Trace script execution")
    return parser.parse_args()


def finalize_testsuite(args):
    global ABORT_EXECUTION
    tr = args["TR"]
    sm = tr.summary()
    for res in sm:
        print("%s%8s%s: %2d" % (ConsoleTestResults.RESULT_COLORS[res],
                                TEST_RESULT_NAMES[res],
                                bcolors.ENDC,
                                sm[res]))

    failed = (sm.setdefault(TEST_NA, 0) +
              sm.setdefault(TEST_ABORTED, 0) +
              sm.setdefault(TEST_FAIL, 0))
    if failed > 0:
        print("\n%sWARNING! NOT ALL TEST PASSED!%s\n" % (
              ConsoleTestResults.RESULT_COLORS[TEST_FAIL], bcolors.ENDC))
    #
    #   Dump report to a JSON file
    #
    if ABORT_EXECUTION:
        print("Test was aborted, don't save data")
        sys.exit(1)

    test_id = args["TEST_ID"]
    f = open("out/bts-test." + test_id + ".json", 'w')
    f.write(tr.json())
    f.close()


##################
#   Main
##################
if __name__ == '__main__':
    TestSuiteConfig.DECORATOR_DEFAULT = def_func_visitor
    # Parse command line arguments
    args = parse_args()

    if args.exclude is not None:
        EXCLUDE_TESTS = args.exclude.split(',')
        print("Exclude list: %s" % str(EXCLUDE_TESTS))

    if args.list:
        for i in TestSuiteConfig.KNOWN_TESTS_DESC.values():
            print("%35s: %-70s" % (i.testname, str(i)))

    TestExecutor.trace_calls = args.trace
    if args.script is not None:
        texec = TestExecutor(open(args.script, "r").read())
        args = {
            "BTS_IP": args.bts_ip,
            "DUT": args.dut,
            "ARFCN": args.arfcn,
            "CMD57_PORT": args.cmd57_port,
            "TR": ConsoleTestResults(),
            "UI": ConsoleUI(),
            "CHAN": ""}
        texec.run(args)
        finalize_testsuite(args)
        sys.exit(0)
