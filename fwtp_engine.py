#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod
from fwtp_core import *
import yaml
import json
import time
import os


class TestResults(metaclass=ABCMeta):
    """
    Class for storing test results and displaying progress
    """

    @abstractmethod
    def output_progress(self, string):
        """
        Output general progress during a test
        :param string: Output string
        :return: None
        """
        pass

    @abstractmethod
    def enter_bundle(self, t, path, bundle, disc):
        """
        Calls when test bundle is being executed
        :param t: Time
        :param path: Test bundle path (bundle01/bundle02/../)
        :param bundle: This bundle name
        :param disc: Bundle discription
        :return: None
        """
        pass

    @abstractmethod
    def print_result(self, t, path, ti, result, value,
                     old_result, old_value, delta, reason):
        """
        Print the result of executing a test
        :param t: Time
        :param path: Path to testsuite (e.g. "/bundle0/bundle1/../testname")
        :param ti: Testuite information (fwtp_core.TestFuncDesc class)
        :param result: Current run test result (see TEST_NA, TEST_OK,
                       TEST_FAILED)
        :param value: Current run test value (e.g actual value of measures
                      power)
        :param old_result: Previous run test result or None if it's the first
        :param old_value: Previous run test value or None if it's the first
        :param delta: Delta between values of current and previous test runs
        :param reason: Reason of failing the test if it's known
        :return: None
        """
        pass

    def __init__(self):
        self.test_results = {}
        self.prev_test_results = {}
        self.scope = 'global'

    def load_prev_data(self, test_id):
        """
        Load historical data matches test_id. Currently loads only the
        newest possible data
        :param test_id: Test identifier to load historical data
        :return: None
        """
        best_file = None
        best_i = -1
        check_string = "bts-test.%s_" % test_id
        for file in os.listdir("out/"):
            i = file.startswith(check_string)
            if i > 0:
                self.output_progress("JSON data found on %s" %
                                     file[i + len(check_string) - 1:-5])
                ddx = [int(x)
                       for x in file[i + len(check_string) - 1:-5].split('-')]
                idx = ((100 * ddx[0] + ddx[1]) *
                       100 + ddx[2]) * 1000000 + ddx[3]
                if idx > best_i:
                    best_i = idx
                    best_file = file
        if best_i == -1:
            self.output_progress(
                'No previous data were found for %s' % test_id)
            return

        self.output_progress('Loading previous data from %s' % best_file)
        with open("out/" + best_file, 'rt', encoding="utf-8") as content:
            self.prev_test_results = json.loads(content.read())
            for scopename in self.prev_test_results:
                curr_scope = self._get_scope_subtree(scopename)
                for testname in self.prev_test_results[scopename]:
                    if testname not in curr_scope:
                        curr_scope[testname] = \
                            self.prev_test_results[scopename][testname]

    def set_test_scope(self, scope):
        """
        Set current testscope being executed
        :param scope: Test scope name
        :return: None
        """
        self.scope = scope

    def clear_test_scope(self, scope):
        """
        Clears testscope test results
        :param scope: Scope to clear test results
        :return: None
        """
        if scope in self.test_results:
            self.test_results[scope] = {}

    def _get_scope_subtree(self, scope=None):
        if scope is None:
            scope = self.scope
        return self.test_results.setdefault(scope, {})

    def skip_test(self, path, ti, skip_result=TEST_NA, reason=None):
        """
        This function is called when test in test bunde is skipped (due to
        exception inside the test being executed or it's manually disable,
        parameter `reason` tells the detail
        :param path: Path of current test
        :param ti: Testuite information (fwtp_core.TestFuncDesc class)
        :param skip_result: Forced value for the skipped test
        :param reason: Human readable reaso to fail the test
        :return: None
        """
        t = time.time()
        delta = None
        old_t, old_result, old_value = self._get_old(path, ti)
        if old_t is not None:
            self._get_scope_subtree()[ti.testname] = (
                old_t, old_result, old_value)
        self.print_result(t, path, ti, skip_result, None,
                          old_result, old_value, delta, reason)

    def _get_old(self, path, ti):
        """
        Return historical tuple of time, test result and test value of the test
        :param path: Path of test being executed
        :param ti: Testuite information (fwtp_core.TestFuncDesc class)
        :return: Tuple (time, test_result, test_value)
        """
        if (len(self.prev_test_results) == 0 or
            self.scope not in self.prev_test_results or
                ti.testname not in self.prev_test_results[self.scope]):
            return None, None, None
        return self.prev_test_results[self.scope][ti.testname]

    def set_test_result(self, path, ti, result, value=None):
        """
        Set the result of the test exectution
        :param path: Path of test being executed
        :param ti: Testuite information (fwtp_core.TestFuncDesc class)
        :param result: Test result (TEST_OK, TEST_FAIL, etc.)
        :param value: Value obtained during execution of the current test
        :return: result
        """
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
        self.print_result(t, path, ti, result, value,
                          old_result, old_value, delta, None)

        return result

    def check_test_result(self, path, ti, value, **kwargs):
        """
        Check the value of the executed test using the helper checker
        function declared in the testsuite decorator (test_*_checker function)
        :param path: Path of test being executed
        :param ti: Testsuite information (fwtp_core.TestFuncDesc class)
        :param value: Value obtained during execution of the current test
        :param kwargs: Set of variable in the execution context
        :return: Test result (TEST_OK, TEST_FAIL, etc.)
        """
        # res = self.checks[ti.testname](value)
        res = ti.CHECK(value, kwargs)
        self.set_test_result(path, ti, res, value)
        return res

    def get_test_result(self, path, ti, scope=None):
        """
        Get tuple of test result for diven test in the specific path
        :param path: Path of the executed test
        :param ti: Testsuite information (fwtp_core.TestFuncDesc class)
        :param scope: Scope where result is stored
        :return: Tuple (time, test_result, test_value)
        """
        return self._get_scope_subtree(scope).get(ti.testname,
                                                  (0, TEST_NA, None))

    def json(self):
        """
        Format JSON with all test results from current run
        :return: JSON string
        """
        return json.dumps(self.test_results,
                          indent=4, separators=(',', ': '))

    def summary(self):
        """
        Get statistics of how many sets failed/succeeded/skipped
        :return: Dictionary { Test result (TEST_OK, TEST_FAIL, etc.) : count }
        """
        stat = {}
        for scopename in self.test_results:
            for testname in self.test_results[scopename].keys():
                tres = self.test_results[scopename][testname]
                if tres is not None:
                    cnt = stat.setdefault(tres[1], 0)
                    stat[tres[1]] = cnt + 1
        return stat


def str2bool(v):
    """
    Helper function transforms v to boolean
    :param v: Boolean or sting
    :return: True if v is bool and true or v in ("yes", "true", "t", "1")
    """
    if isinstance(v, bool):
        return v
    return v.lower() in ("yes", "true", "t", "1")


def apply_subs(string: str, variables: dict) -> str:
    """
    Helper function that substitute {{var}} in string by given values in
    variables dictionary
    :param string: String where to substitute {{...}}
    :param variables: Dictionary of pairs variable - value
    :return: Substituted string
    """
    for key, value in variables.items():
        string = string.replace("{{%s}}" % key, str(value))
    return string


def merge_dicts(base, extention, **extra) -> dict:
    """
    Merge two dictionaries into one with adding extra from kwargs
    :param base: Basic dictionary
    :param extention: Extension of dictionary
    :param extra: Extrs with highest overriding priority
    :return: Combined dictionary
    """
    d = {k: base[k] for k in base.keys()}
    for e in extention.keys():
        d[e] = extention[e]
    for x in extra.keys():
        d[x] = extra[x]
    return d


class TestCaseCall:
    """
    Leaf type for actual test execution. Used to store details of actual
    calling the known decorated function (the testsuite must be in
    TestSuiteConfig.KNOWN_TESTS_DESC)
    """

    def __init__(self, testname, testcallscript=None):
        """
        Initialize the actual test function call.
        :param testname: Test function name (must be in
        TestSuiteConfig.KNOWN_TESTS_DESC)
        :param testcallscript: Dictionary with parameter provided by YAML
        script
        """
        # print("C: %s : %s" % (testname, testcallscript))
        self.enable = True
        self.test = testname
        self.name = testname
        self.desc = testname  # TODO
        self.abort_bundle_on_failure = False
        self.args = None  # no extra args
        self.errors = 0

        if testname not in TestSuiteConfig.KNOWN_TESTS_DESC:
            print("Test `%s` hasn't been found nknown tests" % testname)
            self.errors = self.errors + 1

        if testcallscript is not None:
            self.abort_bundle_on_failure = str2bool(
                testcallscript.get("abort_bundle_on_failure", False))
            self.args = testcallscript.get("args")

    def __str__(self):
        return self.test

    def run(self, path, kwargs):
        """
        Run the specific test.
        :param path: Path of the test inside the executor
        :param kwargs: Dictionary of specified variables
        :return: False if test was aborted, True otherwise
        """
        ti = TestSuiteConfig.KNOWN_TESTS_DESC[self.test]
        dut = kwargs.get("DUT")
        if not self.enable:
            kwargs["TR"].output_progress(
                "Test %s in %s bundle is disabled" % (self.test, path))
            return True
        if dut is not None and ti.check_dut(dut):
            if TestExecutor.trace_calls:
                kwargs["TR"].output_progress(
                    "Calling %s/%s -> %s()" % (path, self.test,
                                               ti.func.__name__))

            res = TestSuiteConfig.DECORATOR_DEFAULT(path, ti, kwargs)
            if self.abort_bundle_on_failure and res != TEST_OK:
                kwargs["TR"].output_progress(
                    ("Test %s failed which also fails " +
                     "whole %s bundle") % (self.test, path))
                return False
        else:
            kwargs["TR"].skip_test(path, ti, TEST_NA,
                                   ("Function %s in bundle %s isn't " +
                                    "compatible with DUT:%s, " +
                                    "ignoring") % (ti.func.__name__,
                                                   self.name, dut))
        return True


class TestRepeat:
    """
    Repeat the same test bundle or another repeat block specified amount
    """

    def __init__(self, repeatscript):
        """
        Initialize the repeat block. The repeat block must have
        'count' parameter specifies exact number of cycles or form a
        dictionary of values to iterate. The iteration variable 'ITER' will be
        set to "${ITER}/${curent_variable}". So 'ITER' has the all values of
        inner repeat blocks. To get the current iteration value you need to
        get the latest value after '/' symbol.
        :param repeatscript: YAML string representing the repeat script
        """
        # print ("R: %s" % repeatscript)
        self.enable = True
        self.errors = 0
        self.name = repeatscript.get("name", "<repeat>")
        self.desc = repeatscript.get("description", self.name)
        self.args = repeatscript.get("args")
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
        """
        Run repeat block. Before entering the child leaves we set 'ITER'
        variable.
        :param path: Path of the test inside the executor
        :param kwargs: Dictionary of specified variables
        :return: False if test was aborted, True otherwise
        """
        if not self.enable:
            return True
        i = 0
        if self.args is not None:
            for a in self.args:
                ea = {k: apply_subs(a[k], kwargs) if isinstance(
                    a[k], str) else a[k] for k in a.keys()}
                self.execute.run("%s/%s@%s" % (path, self.name, ea),
                                 merge_dicts(kwargs, ea,
                                             ITER="%s/%d" % (kwargs["ITER"],
                                                             i)))
                i += 1


class TestBundle:
    """
    Test bundle parser. Called by top level TestExecutor or any other leaf.
    Bundle can consist another Bundle or repeat block or specific test call.
    """

    def __init__(self, bundlescript):
        """
        Initialize the test bundle
        :param bundlescript: YAML string representing the whole test bundle
        """
        # print ("B: %s" % bundlescript)
        self.enable = True
        self.name = bundlescript["name"]
        self.desc = bundlescript.get("description", self.name)
        self.scope = bundlescript.get("scope", "global")
        self.tests = []
        self.errors = 0
        for test in bundlescript["testsuites"]:
            self.errors = self.errors + self._checktests(test)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "Name: %s, Desc: '%s', tests: '%s'" % (self.name,
                                                      self.desc, self.tests)

    def _checktests(self, testscript):
        """
        Validates the pased script and if it's OK add it to our list of
        execution. This function recursively calls initialization to all leaves
        :param testscript: Subtree of the script. Parsed YAML structure.
        :return: Number of errors during parsing
        """
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
        """
        Run the execution of underlying test and bundles.
        :param path: Path of the test inside the executor
        :param kwargs: Dictionary of specified variables
        :return: False if test bundle was aborted, otherwise True
        """
        if not self.enable:
            return True

        scope = apply_subs(self.scope, kwargs)
        kwargs["TR"].set_test_scope(scope)
        kwargs["TR"].enter_bundle(time.time(), path, self.name, self.desc)
        for t in self.tests:
            if not t.run("%s/%s" % (path, self.name), kwargs):
                # Bundle aborted
                return False
        return True


class TestExecutor:
    """
    Main test executor class. All YAML test scrips are handled by this
    class. All child subcalls are handled inside.
    """

    trace_calls = False

    def __init__(self, testscript):
        """
        Initialize the test script
        :param testscript:  YAML string representing the whole test bundle
        """
        self.yamltree = yaml.load(testscript)
        self.bundles = []
        self.errors = 0

        for i in self.yamltree:
            self._initbundle(i)

        if self.errors > 0:
            raise RuntimeError(
                "Got %d errors in testscript, aborting" % self.errors)

    def _initbundle(self, bundletree):
        """
        Top level script initializer. Top level must be comprised of
        "bundle" type only. It does recursion down to the leaf during
        initialization.
        :param bundletree: Subtree of the script. Parsed YAML structure.
        :return: None
        """
        if "bundle" in bundletree:
            # try:
            bundle = TestBundle(bundletree["bundle"])
            self.bundles.append(bundle)
            self.errors = self.errors + bundle.errors
            # except:
            #    self.errors = self.errors + 1
            #    print ("Bundle '%s' contains errors" % bundletree["bundle"])
        else:
            self.errors = self.errors + 1
            print("Parsing error, don't know how to handle: %s" % bundletree)

    def run(self, args):
        """
        Run test execution with spicified variables in args. All tests a
        relied on specific variables:
        'TR' - instance of TestResults class to do the progress
        'DUT' - actual DUT being tested (for test compatibility checks)
        'ITER' - internal variable to store iteration variable over the
                 repeat block. Will be overriden if it was set

        :param args: Dictionary of specified variables
        :return: None
        """
        if TestExecutor.trace_calls:
            args["TR"].output_progress(
                "Run testsuite with global variables: `%s`" % args)
        args["ITER"] = ""
        for b in self.bundles:
            if TestExecutor.trace_calls:
                args["TR"].output_progress("Executing bundle: %s" % b)
            b.run("", args)
