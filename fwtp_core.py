#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# FW Test Platform core file
#
#

""" Core test module. Defines common constnats """

from functools import wraps

TEST_NA = -1
TEST_ABORTED = 0
TEST_OK = 1
TEST_FAIL = 2

TEST_RESULT_NAMES = {
    TEST_NA: "N/A",
    TEST_ABORTED: "ABORTED",
    TEST_OK: "OK",
    TEST_FAIL: "FAIL"
}

# checkers


def evaluate_dut_check(x):
    """
    Function to be used in a decorator to do dynamic evaluation from
    DUT_CHECKS map
    """
    return lambda args: (args["DUT_CHECKS"])[x]


def test_none_checker():
    """
    Decorator test check function
    :return: TEST_OK if the checking test returns not None
    """
    return lambda val, args: TEST_OK if val is not None \
        else TEST_FAIL


def test_bool_checker():
    """
    Decorator test check function
    :return: TEST_OK if the checking test returns True
    """
    return lambda val, args: TEST_OK if val is not None and val \
        else TEST_FAIL


def test_val_checker(val_ok):
    """
    Decorator test check function
    :param val_ok: Expecting return value of the test
    :return: TEST_OK if the checking test returns val_ok
    """
    return lambda val, args: \
        TEST_OK if val is not None and val == val_ok \
        else TEST_FAIL


def test_list_checker(val_ok_list):
    """
    Decorator test check function
    :param val_ok_list: List of expecting values of the test
    :return: TEST_OK if the checking test returns any value in val_ok_list
    """
    return lambda val, args: \
        TEST_OK if val is not None and val in val_ok_list \
        else TEST_FAIL


def test_minmax_checker(min, max):
    """
    Decorator test check function
    :param min: Minimum expecting values of the test
    :param max: Maximum expecting values of the test
    :return: TEST_OK if the checking test returns value between min and max
    """
    return lambda val, args: TEST_OK if val is not None and \
        (val >= (min(args) if callable(min) else min)) and \
        (val <= (max(args) if callable(max) else max)) \
        else TEST_FAIL


def test_abs_checker(valabs):
    """
    Decorator test check function
    :param valabs: Absolute maximum expecting value of the test
    :return: TEST_OK if the absolute value of the checking test is less or
    equal to valabs
    """
    return lambda val, args: TEST_OK if val is not None and \
        abs(val) <= (valabs(args) if callable(valabs) else valabs) \
        else TEST_FAIL


def test_ignore_checker():
    """
    Decorator test check function
    :return: Always returns TEST_OK
    """
    return lambda val, args: TEST_OK


def test_substr_checker(okstr):
    """
    Decorator test check function
    :param okstr: Expecting substring in the return of the test
    :return: TEST_OK if okstr is found in the return string of the test
    """
    return lambda val, args: TEST_OK if \
        (okstr(args) if callable(okstr) else okstr).find(val) != -1 \
        else TEST_FAIL


class TestSuiteConfig:
    """ Global TestSuite configuration of all known tests and their
    structure """

    DECORATOR_DEFAULT = None
    KNOWN_TESTS_DESC = {}
    CALLER_PATH = "/"


class TestFuncDesc:
    """
    Parsed data from test_checker_decorator() decorator
    """

    def __init__(self, testname, func, **kwargs):
        """
        Initialize data from dictionary
        :param testname: Unique name of the test in the system
        :param func:  Testsuite function
        :param kwargs: Dictionary of parameters:
            "DUT" - Device under test compatibility list
            "INFO" - Human readable description
            "CHECK" - Checker function
        """
        self.testname = testname
        self.func = func
        self.DUT = kwargs["DUT"] if "DUT" in kwargs else None
        self.INFO = kwargs["INFO"] if "INFO" in kwargs else testname
        self.CHECK = kwargs["CHECK"] if "CHECK" in kwargs \
            else test_none_checker()

    def check_dut(self, dut):
        """
        Check whether current test run is suitable for declared compatibility
        list
        :param dut: test run for this spcific DUT
        :return: True if dut is supported
        """
        if self.DUT is not None:
            return dut in self.DUT
        return True

    def __repr__(self):
        """ return "INFO" in decoration as a representation """
        return self.INFO


def test_checker_decorator(testname, **kwargs):
    """ Wrapper function for all testsuites """

    def real_decorator(func):
        TestSuiteConfig.KNOWN_TESTS_DESC[testname] = TestFuncDesc(
            testname, func, **kwargs)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return TestSuiteConfig.DECORATOR_DEFAULT(
                TestSuiteConfig.CALLER_PATH,
                TestSuiteConfig.KNOWN_TESTS_DESC[testname],
                *args, **kwargs)
        return wrapper
    return real_decorator
