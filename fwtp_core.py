#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# FW Test Platform core file
#
#
from functools import wraps

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

# checkers
def evaluate_dut_check(x):
    return lambda args: (args["DUT_CHECKS"])[x]


def test_none_checker():
    return lambda val, args: TEST_OK if val is not None \
                               else TEST_FAIL


def test_bool_checker():
    return lambda val, args: TEST_OK if val is not None and val \
                               else TEST_FAIL


def test_val_checker(val_ok):
    return lambda val, args: TEST_OK if val is not None and val == val_ok \
                               else TEST_FAIL


def test_list_checker(val_ok_list):
    return lambda val, args: TEST_OK if val is not None and val in val_ok_list \
                               else TEST_FAIL


def test_minmax_checker(min, max):
    return lambda val, args: TEST_OK if val is not None and \
                                  val >= (min(args) if callable(min) else min) and \
                                  val <= (max(args) if callable(max) else max) \
                               else TEST_FAIL

def test_abs_checker(limit):
    return lambda val, args: TEST_OK if val is not None and \
                                  abs(val) <= (limit(args) if callable(limit) else limit) \
                               else TEST_FAIL

def test_ignore_checker():
    return lambda val, args: TEST_OK


def test_substr_checker(okstr):
    return lambda val, args: TEST_OK if (okstr(args) if callable(okstr) else okstr).find(val) != -1 \
                               else TEST_FAIL

class TestSuiteConfig:
    DECORATOR_DEFAULT = lambda path, ti, args:  args["TR"].check_test_result(path, ti, ti.func(args), args)
    KNOWN_TESTS_DESC  = {}
    CALLER_PATH = "/"

class TestFuncDesc:
    def __init__(self, testname, func, **kwargs):
        self.testname = testname
        self.func = func
        self.DUT = kwargs.get("DUT")
        self.INFO = kwargs.get("INFO", testname)
        self.CHECK = kwargs.get("CHECK", test_none_checker())

    def check_dut(self, dut):
        if self.DUT is not None:
            return dut in self.DUT
        return True

def test_checker_decorator(testname, **kwargs):
    def real_decorator(func):
        TestSuiteConfig.KNOWN_TESTS_DESC[testname] = TestFuncDesc(testname, func, **kwargs)

        @wraps(func)
        def wrapper(args):
            return TestSuiteConfig.DECORATOR_DEFAULT( TestSuiteConfig.CALLER_PATH, TestSuiteConfig.KNOWN_TESTS_DESC[testname], args)
        return wrapper
    return real_decorator


