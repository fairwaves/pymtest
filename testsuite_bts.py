#!/usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
from scpi.devices import cmd57_console as cmd57
# from scpi.errors import TimeoutError

from fwtp_core import *
import time

###############################
#  DUT connection
###############################
import paramiko
import subprocess
import re

from abc import ABCMeta, abstractmethod


class BtsControlBase(metaclass=ABCMeta):
    """
    Base class for the BTS control
    """

    helpers = ["obscvty.py", "osmobts-en-loopback.py",
               "osmobts-set-maxdly.py", "osmobts-set-slotmask.py",
               "osmo-trx-primary-trx.py", "umtrx_set_dcdc_r.py",
               "umtrx_get_vswr_sensors.py",
               # TODO: Move this from helpers to packages
               "umtrx_property_tree.py",
               "umtrx_ctrl.py", "umtrx_lms.py"]

    locals = ["test_umtrx_reset.py", "test_umtrx_gps_time.py"]

    @abstractmethod
    def _exec(self, cmd_str):
        """ Execute command on the DUT """
        pass

    @abstractmethod
    def _copy_file_list(self, dir_from, flie_list, dir_to):
        """
        Copy local files to the DUT
        :param dir_from: Directory to copy files from
        :param flie_list: Files to copy
        :param dir_to: Directory on the DUT to copy files on
        :return: None
        """
        pass

    @abstractmethod
    def _exec_stdout_b(self, cmd_str):
        """
        Execute command and get array of lines of bytes from stdout
        :param cmd_str: command to execute
        :return: array of lines of bytes
        """
        return []

    @abstractmethod
    def _exec_stdout_stderr_b(self, cmd_str):
        """
        Execute command and get array of lines of bytes from stdout + stderr
        :param cmd_str: command to execute
        :return: array of lines of bytes
        """
        return []

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        """" Connect to a BTS and prepare it for testing """
        # Copy helper scripts to the BTS
        self.tmpdir = tmpdir
        self._exec_stdout('mkdir -p ' + self.tmpdir)
        self._copy_file_list('helper/', self.helpers, self.tmpdir)
        self._copy_file_list('./', self.locals, self.tmpdir)
        self.sudo = sudopkg

    @staticmethod
    def _tee(stream, filename):
        """ Write lines from the stream to the file and return the lines """
        lines = [i if type(i) is str else i.decode("utf-8")
                 for i in stream.readlines()]
        f = open(filename, 'w')
        f.writelines(lines)
        f.close()
        return lines

    def get_uname(self):
        """ Get uname string """
        return self._exec_stdout('uname -a')[0].strip()

    def trx_set_primary(self, num):
        """ Set primary TRX """
        print("Setting primary TRX to TRX%d" % num)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python osmo-trx-primary-trx.py %d' % (self.sudo, num))

    def bts_en_loopback(self):
        """ Enable loopbak in the BTS """
        print("Enabling BTS loopback")
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-en-loopback.py')

    def bts_set_slotmask(self, ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7):
        """ Set BTS TRX0 slotmask """
        print("Setting BTS slotmask")
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-slotmask.py %d %d %d %d %d %d %d %d'
            % (ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7))

    def umtrx_get_gps_time(self):
        """Obtain time diff GPS vs system"""
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python3 test_umtrx_gps_time.py' % self.sudo)

    def bts_get_hw_config(self, param):
        """ Get hardware configuration parameter """
        return self._exec_stdout_stderr(
            'cat /etc/osmocom/hardware.conf | grep %s | cut -d= -f2' % param)

    def bts_set_maxdly(self, val):
        """ Set BTS TRX0 max timing advance """
        print("BTS: setting max delay to %d." % val)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python osmobts-set-maxdly.py %d' % val)

    def bts_led_blink(self, period=1):
        """ Continously blink LED """
        return self._exec_stdout_stderr(
            '%s umsite-led-blink_%dhz.sh' % (self.sudo, period))

    def bts_led_on(self, on=1):
        """ On or off system LED"""
        return self._exec_stdout_stderr(
            '%s umsite-led-on-%s.sh' % (self.sudo, 'on' if on else 'off'))

    def bts_shutdown(self):
        """ Shutdown BTS host """
        return self._exec_stdout_stderr(
            '%s shutdown -h now' % self.sudo)

    def umtrx_reset_test(self):
        """ Do umtrx reset and get console output form it """
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            '%s python3 test_umtrx_reset.py' % self.sudo)

    def umtrx_set_dcdc_r(self, val):
        """ Set UmTRX DCDC control register value """
        # print("UmTRX: setting DCDC control register to %d." % val)
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_set_dcdc_r.py %d' % val)

    def umtrx_set_tx_vga2(self, chan, val):
        """ Set UmTRX Tx VGA2 gain """
        # print("UmTRX: setting UmTRX Tx VGA2 gain for chan %d to %d." %
        #       (chan, val))
        return self._exec_stdout_stderr(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_lms.py --lms %d --lms-set-tx-vga2-gain %d'
            % (chan, val))

    def umtrx_get_vswr_sensors(self, chan):
        """ Read UmTRX VPR and VPF sensors """
        lines = self._exec_stdout(
            'cd ' + self.tmpdir + '; ' +
            'python umtrx_get_vswr_sensors.py')
        res = [float(x.strip()) for x in lines]
        start = (chan - 1) * 2
        return res[start:start + 2]

    def start_runit_service(self, service):
        """ Start a runit controlled service """
        print("Starting '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv start %s' % (self.sudo, service))
        # TODO: Check result

    def stop_runit_service(self, service):
        """ Stop a runit controlled service """
        print("Stopping '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv stop %s' % (self.sudo, service))
        # TODO: Check result

    def restart_runit_service(self, service):
        """ Restart a runit controlled service """
        print("Restarting '%s' service." % service)
        return self._exec_stdout_stderr(
            '%s sv restart %s' % (self.sudo, service))
        # TODO: Check result

    def osmo_trx_start(self):
        """ Start omso-trx service """
        return self.start_runit_service("osmo-trx")

    def osmo_trx_stop(self):
        """ Stop osmo-trx service """
        return self.stop_runit_service("osmo-trx")

    def osmo_trx_restart(self):
        """ Restart osmo-trx service """
        return self.restart_runit_service("osmo-trx")

    def get_umtrx_eeprom_val(self, name):
        """ Read UmTRX serial from EEPROM.
            All UHD apps should be stopped at the time of reading. """
        lines = self._exec_stdout_stderr(
            '/usr/lib/uhd/utils/usrp_burn_mb_eeprom --values "serial"')
        eeprom_val = re.compile(r' {4}EEPROM \["' + name + r'"\] is "(.*)"')
        for s in lines:
            match = eeprom_val.match(s)
            if match is not None:
                return match.group(1)
        return None

    def umtrx_autocalibrate(self, preset, filename_stdout, filename_stderr):
        """ Run UmTRX autocalibration for the selected band.
            preset - One or more of the following space seprated values:
                     GSM850, EGSM900 (same as GSM900),
                     GSM1800 (same as DCS1800), GSM1900 (same as PCS1900)
            All UHD apps should be stopped at the time of executing. """
        stdin, stdout, stderr = self._exec(
            '%s umtrx_auto_calibration %s' % (self.sudo, preset))
        # TODO: Check result
        lines = self._tee(stdout, filename_stdout)
        self._tee(stderr, filename_stderr)
        line_re = re.compile(
            r'Calibration type .* side . from .* to .*: ([A-Z]+)')
        if len(lines) == 0:
            return False

        for l in lines:
            match = line_re.match(l)
            if match is not None:
                if match.group(1) != 'SUCCESS':
                    return False
        return True

    def _exec_stdout(self, cmd_str):
        """ return array of string from execution _exec_stdout_b """
        barrs = self._exec_stdout_b(cmd_str)
        print(barrs)
        return [i if type(i) is str else i.decode("utf-8") for i in barrs]

    def _exec_stdout_stderr(self, cmd_str):
        """ return array of string from execution _exec_stdout_stderr_b """
        barrs = self._exec_stdout_stderr_b(cmd_str)
        print(barrs)
        return [i if type(i) is str else i.decode("utf-8") for i in barrs]


class BtsControlSsh(BtsControlBase):

    def __init__(self, bts_ip, port=22, username='', password='',
                 tmpdir='/tmp/bts-test'):
        """ Connect to a BTS and prepare it for testing """
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(bts_ip, port=port, username=username,
                         password=password, timeout=2)
        BtsControlBase.__init__(self, tmpdir)

    def _exec_stdout_b(self, cmd_str):
        raise Exception('Incorrect usage!')

    def _exec_stdout_stderr_b(self, cmd_str):
        raise Exception('Incorrect usage!')

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        sftp = self.ssh.open_sftp()
        for f in flie_list:
            sftp.put(dir_from + f, dir_to + '/' + f)
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
    """
    Local manual control class
    """

    def __init__(self, ui, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        """ Connect to a BTS and prepare it for testing """
        BtsControlBase.__init__(self, tmpdir, sudopkg)
        self.ui = ui

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        for f in flie_list:
            subprocess.check_call(["cp", dir_from + f, dir_to + '/' + f])

    def _exec(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        return p.stdin, p.stdout, p.stderr

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
        return self.ui.ask("Please start osmo-trx")

    def osmo_trx_stop(self):
        return self.ui.ask("Please stop osmo-trx")

    def osmo_trx_restart(self):
        return self.ui.ask("Please restart osmo-trx")


class BtsControlLocal(BtsControlBase):
    """
    Local sv-based service BTS control
    """

    def __init__(self, tmpdir='/tmp/bts-test', sudopkg='sudo'):
        """ Connect to a BTS and prepare it for testing """
        BtsControlBase.__init__(self, tmpdir, sudopkg)

    def _copy_file_list(self, dir_from, flie_list, dir_to):
        for f in flie_list:
            subprocess.check_call(["cp", dir_from + f, dir_to + '/' + f])

    def _exec(self, cmd_str):
        p = subprocess.Popen(cmd_str,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        return p.stdin, p.stdout, p.stderr

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


@test_checker_decorator("bts_connection",
                        INFO="Establishing connection with the BTS")
def test_bts_connection(kwargs):
    bts_ip = kwargs["BTS_IP"] if "BTS_IP" in kwargs else "local"
    dut_checks = kwargs["DUT_CHECKS"]
    if bts_ip == "local":
        bts = BtsControlLocal()
    elif bts_ip == "manual":
        bts = BtsControlLocalManual(kwargs["UI"])
    else:
        bts = BtsControlSsh(
            bts_ip, 22, dut_checks['login'], dut_checks['password'])

    kwargs["BTS"] = bts
    return str(bts)

###############################
#   non-CMD57 based tests
###############################


@test_checker_decorator("bts_hw_model",
                        INFO="BTS hardware model",
                        CHECK=test_substr_checker(
                            evaluate_dut_check("hw_model")))
def bts_hw_model(kwargs):
    return kwargs["BTS"].bts_get_hw_config('HW_MODEL')[0].strip('\n')


@test_checker_decorator("bts_hw_band",
                        INFO="BTS hardware band")
def bts_hw_band(kwargs):
    return kwargs["BTS"].bts_get_hw_config('BAND')[0].strip('\n')


@test_checker_decorator("bts_umtrx_ver",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="BTS umtrx ver")
def bts_umtrx_ver(kwargs):
    return kwargs["BTS"].bts_get_hw_config('UMTRX_VER')[0].strip('\n')


@test_checker_decorator("umtrx_reset_test",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="UmTRX Reset and Safe firmware loading test",
                        CHECK=test_bool_checker())
def umtrx_reset_test(kwargs):
    lns = kwargs["BTS"].umtrx_reset_test()
    kwargs["TR"].output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1


@test_checker_decorator("umtrx_gps_time",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="UmTRX GPS time",
                        CHECK=test_bool_checker())
def umtrx_gps_time(kwargs):
    lns = kwargs["BTS"].umtrx_get_gps_time()
    kwargs["TR"].output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1


@test_checker_decorator("bts_uname",
                        INFO="BTS system information")
def bts_read_uname(kwargs):
    bts_uname = kwargs["BTS"].get_uname()
    kwargs["BTS_UNAME"] = bts_uname
    return bts_uname


@test_checker_decorator("set_primary_trx",
                        INFO="Set Primary TRX for osmo-trx")
def set_primary_trx(kwargs):
    chan = kwargs["CHAN"]
    kwargs["BTS"].trx_set_primary(chan)
    return chan


@test_checker_decorator("restart_osmo_trx",
                        INFO="Restart osmo-trx service")
def restart_osmo_trx(kwargs):
    return kwargs["BTS"].osmo_trx_restart()


@test_checker_decorator("umtrx_serial",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="UmTRX serial number")
def bts_read_umtrx_serial(kwargs):
    umtrx_serial = kwargs["BTS"].get_umtrx_eeprom_val("serial")
    kwargs["UMTRX_SERIAL"] = umtrx_serial
    return umtrx_serial


@test_checker_decorator("test_id")
def gen_test_id(kwargs):
    """ Generates a unique test ID """
    tr = kwargs["TR"]
    uname_res = kwargs["BTS_UNAME"]
    serial_res = kwargs["UMTRX_SERIAL"]
    name = uname_res.split()[1]
    timestr = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(time.time()))
    fixed_test_id = name + '_' + serial_res
    tr.load_prev_data(fixed_test_id)
    test_id = fixed_test_id + '_' + timestr
    kwargs["TEST_ID"] = test_id
    return test_id


@test_checker_decorator("test_id2")
def gen_test_id2(kwargs):
    """ Generates a unique test ID """
    tr = kwargs["TR"]
    uname_res = kwargs["BTS_UNAME"]
    tr.output_progress("DUT: uname: '%s'" % uname_res)
    name = uname_res.split()[1]
    timestr = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(time.time()))
    fixed_test_id = name
    tr.load_prev_data(fixed_test_id)
    test_id = fixed_test_id + '_' + timestr
    kwargs["TEST_ID"] = test_id
    return test_id


@test_checker_decorator("umtrx_autocalibrate",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="UmTRX autocalibration",
                        CHECK=test_bool_checker())
def bts_umtrx_autocalibrate(bts, preset, filename_stdout, filename_stderr):
    return bts.umtrx_autocalibrate(preset, filename_stdout, filename_stderr)


###############################
#   CMD57 based tests
###############################

@test_checker_decorator("cmd57_init",
                        INFO="Initialize CMD57")
def test_cmd57_init(kwargs):
    cmd57_port = kwargs.get("CMD57_PORT", "/dev/ttyUSB0")
    dev = cmd57.rs232(cmd57_port, rtscts=True)
    kwargs["CMD"] = dev
    atexit.register(dev.quit)
    return str(dev)


@test_checker_decorator("tester_name",
                        INFO="Tester device name")
def test_tester_id(kwargs):
    id_str = kwargs["CMD"].identify()
    name = id_str[0] + ' ' + id_str[1]
    return name


@test_checker_decorator("tester_serial",
                        INFO="Tester serial")
def test_tester_id(kwargs):
    id_str = kwargs["CMD"].identify()
    return id_str[2]


@test_checker_decorator("tester_version",
                        INFO="Tester veersion")
def test_tester_id(kwargs):
    id_str = kwargs["CMD"].identify()
    return id_str[3]


@test_checker_decorator("tester_options",
                        INFO="Tester installed options")
def test_tester_options(kwargs):
    return " ".join(kwargs["CMD"].ask_installed_options())


@test_checker_decorator("burst_power_peak",
                        INFO="TRX output power (dBm)",
                        CHECK=test_minmax_checker(
                            evaluate_dut_check("burst_power_peak_min"),
                            evaluate_dut_check("burst_power_peak_max")))
def test_burst_power_peak(kwargs):
    """ Check output power level """
    return kwargs["CMD"].ask_peak_power()


@test_checker_decorator("burst_power_peak_wait",
                        INFO="Wait for TRX output power (dBm)",
                        CHECK=test_val_checker(TEST_OK))
def test_burst_power_peak_wait(kwargs):
    """ Wait for output power level """
    timeout = kwargs["TIMEOUT"] if "TIMEOUT" in kwargs else 20
    res = TEST_NA
    t = time.time()
    while res != TEST_OK and time.time() - t < timeout:
        res = test_burst_power_peak(kwargs)
        if res == TEST_ABORTED:
            return res
    res = test_burst_power_peak(kwargs)
    return res


@test_checker_decorator("bcch_presence",
                        INFO="BCCH detected",
                        CHECK=test_bool_checker())
def test_bcch_presence(kwargs):
    """ Check BCCH presence """
    cmd = kwargs["CMD"]
    cmd.switch_to_man_bbch()
    return cmd.ask_dev_state() == "BBCH"

#
# Burst power, phase and frequency tests
#


@test_checker_decorator("burst_power_avg",
                        INFO="Burst avg power (dBm)",
                        CHECK=test_minmax_checker(
                            evaluate_dut_check("burst_power_avg_min"),
                            evaluate_dut_check("burst_power_avg_max")))
def test_burst_power_avg(kwargs):
    return kwargs["CMD"].ask_burst_power_avg()


@test_checker_decorator("burst_power_array",
                        INFO="Burst power array (dBm)")
def test_burst_power_array(kwargs):
    return kwargs["CMD"].ask_burst_power_arr()


@test_checker_decorator("freq_error",
                        INFO="Frequency error (Hz)",
                        CHECK=test_abs_checker(
                            evaluate_dut_check("freq_error")))
def test_freq_error(kwargs):
    return kwargs["CMD"].ask_freq_err()


@test_checker_decorator("phase_err_array",
                        INFO="Phase error array (deg)")
def test_phase_err_array(kwargs):
    return kwargs["CMD"].ask_phase_err_arr()


@test_checker_decorator("phase_err_pk",
                        INFO="Phase error peak (deg)",
                        CHECK=test_minmax_checker(
                            evaluate_dut_check("phase_err_pk_min"),
                            evaluate_dut_check("phase_err_pk_max")))
def test_phase_err_pk(kwargs):
    return kwargs["CMD"].fetch_phase_err_pk()


@test_checker_decorator("phase_err_avg",
                        INFO="Phase error avg (deg)",
                        CHECK=test_minmax_checker(
                            evaluate_dut_check("phase_err_avg_min"),
                            evaluate_dut_check("phase_err_avg_max")))
def test_phase_err_avg(kwargs):
    return kwargs["CMD"].fetch_phase_err_rms()

#
# Spectrum tests
#


@test_checker_decorator("spectrum_modulation_offsets",
                        INFO="Modulation spectrum measurement offsets (kHz)")
def test_spectrum_modulation_offsets(kwargs):
    return kwargs["CMD"].fetch_spectrum_modulation_offsets()


@test_checker_decorator("spectrum_modulation_tolerance_abs",
                        INFO="Modulation spectrum absolute " +
                             "tolerance mask (dBm)")
def test_spectrum_modulation_tolerance_abs(kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_tolerance_abs()


@test_checker_decorator("spectrum_modulation_tolerance_rel",
                        INFO="Modulation spectrum relative " +
                             "tolerance mask (dBc)")
def test_spectrum_modulation_tolerance_rel(kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_tolerance_rel()


@test_checker_decorator("spectrum_modulation",
                        INFO="Modulation spectrum measured (dBc)")
def test_spectrum_modulation(kwargs):
    return kwargs["CMD"].ask_spectrum_modulation()


@test_checker_decorator("spectrum_modulation_match",
                        INFO="Modulation spectrum match",
                        CHECK=test_val_checker("MATC"))
def test_spectrum_modulation_match(kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_match()


@test_checker_decorator("spectrum_switching_offsets",
                        INFO="Switching spectrum measurement offsets (kHz)")
def test_spectrum_switching_offsets(kwargs):
    return kwargs["CMD"].fetch_spectrum_switching_offsets()


@test_checker_decorator("spectrum_switching_tolerance_abs",
                        INFO="Switching spectrum absolute tolerance " +
                             "mask (dBm)")
def test_spectrum_switching_tolerance_abs(kwargs):
    return kwargs["CMD"].ask_spectrum_switching_tolerance_abs()


@test_checker_decorator("spectrum_switching_tolerance_rel",
                        INFO="Switching spectrum relative tolerance mask " +
                             "(dBc)")
def test_spectrum_switching_tolerance_rel(kwargs):
    return kwargs["CMD"].ask_spectrum_switching_tolerance_rel()


@test_checker_decorator("spectrum_switching",
                        INFO="Switching spectrum measured (dBc)")
def test_spectrum_switching(kwargs):
    return kwargs["CMD"].ask_spectrum_switching()


@test_checker_decorator("spectrum_switching_match",
                        INFO="Switching spectrum match")
def test_spectrum_switching_match(kwargs):
    return kwargs["CMD"].ask_spectrum_switching_match()

#
# BER test settings
#


@test_checker_decorator("ber_configure",
                        INFO="BER test configuration",
                        CHECK=test_ignore_checker())
def test_ber_configure(kwargs):
    cmd = kwargs["CMD"]
    dut_checks = kwargs["DUT_CHECKS"]
    if "ber_unused_ts_power" in kwargs:
        ber_unused_ts_power = kwargs["ber_unused_ts_power"]
    elif "ber_unused_ts_power" in dut_checks:
        ber_unused_ts_power = dut_checks["ber_unused_ts_power"]
    else:
        ber_unused_ts_power = 30
    cmd.set_ber_unused_ts_power(ber_unused_ts_power)

    if "ber_used_ts_power" in kwargs:
        ber_used_ts_power = kwargs["ber_used_ts_power"]
    elif "ber_unused_ts_power" in dut_checks:
        ber_used_ts_power = dut_checks["ber_used_ts_power"]
    else:
        ber_used_ts_power = -104
    cmd.set_ber_used_ts_power(ber_used_ts_power)

    ber_test_num = dut_checks["ber_test_num"] if \
        "ber_test_num" in dut_checks else 1
    return cmd.set_ber_test_num(ber_test_num)


@test_checker_decorator("ber_used_ts_power",
                        INFO="Used TS power (dBm)")
def test_ber_used_ts_power(kwargs):
    return kwargs["CMD"].ask_ber_used_ts_power()


@test_checker_decorator("ber_unused_ts_power",
                        INFO="Unused TS power (dBm)")
def test_ber_unused_ts_power(kwargs):
    return kwargs["CMD"].ask_ber_unused_ts_power()


@test_checker_decorator("ber_frames_num",
                        INFO="Frames to send")
def test_ber_frames_num(kwargs):
    return kwargs["CMD"].ask_ber_frames_num()


@test_checker_decorator("ber_max_test_time",
                        INFO="Test time")
def test_ber_max_test_time(kwargs):
    return kwargs["CMD"].ask_ber_max_test_time()


@test_checker_decorator("ber_abort_condition",
                        INFO="Abort condition")
def test_ber_abort_condition(kwargs):
    return kwargs["CMD"].ask_ber_abort_cond()


@test_checker_decorator("ber_holdoff_time",
                        INFO="Hold-off time")
def test_ber_holdoff_time(kwargs):
    return kwargs["CMD"].ask_ber_holdoff_time()


@test_checker_decorator("ber_limit_class_1b",
                        INFO="Class Ib bit errors tolerance (%)")
def test_ber_limit_class_1b(kwargs):
    return kwargs["CMD"].ask_ber_limit_class_1b()


@test_checker_decorator("ber_max_class_1b_samples",
                        INFO="Class Ib bit errors max number")
def test_ber_max_class_1b_samples(kwargs):
    return kwargs["CMD"].ask_ber_max_class_1b_samples()


@test_checker_decorator("ber_limit_class_2",
                        INFO="Class II bit errors tolerance (%)")
def test_ber_limit_class_2(kwargs):
    return kwargs["CMD"].ask_ber_limit_class_2()


@test_checker_decorator("ber_max_class_2_samples",
                        INFO="Class II bit errors max number")
def test_ber_max_class_2_samples(kwargs):
    return kwargs["CMD"].ask_ber_max_class_2_samples()


@test_checker_decorator("ber_limit_erased_frames",
                        INFO="Erased frames tolerance (%)")
def test_ber_limit_erased_frames(kwargs):
    return kwargs["CMD"].ask_ber_limit_erased_frames()


@test_checker_decorator("ber_max_erased_frames_samples",
                        INFO="Erased frames max number")
def test_ber_max_erased_frames_samples(kwargs):
    return kwargs["CMD"].ask_ber_max_erased_frames_samples()

#
# BER test results
#


@test_checker_decorator("ber_test_result",
                        INFO="BER test result",
                        CHECK=test_val_checker("PASS"))
def test_ber_test_result(kwargs):
    return kwargs["CMD"].read_ber_test_result()


@test_checker_decorator("ber_class_1b_events",
                        INFO="Class Ib bit error events")
def test_ber_class_1b_events(kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_events()


@test_checker_decorator("ber_class_1b_ber",
                        INFO="Class Ib bit error rate (%)")
def test_ber_class_1b_ber(kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_ber()


@test_checker_decorator("ber_class_1b_rber",
                        INFO="Class Ib bit residual error rate (%)")
def test_ber_class_1b_rber(kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_rber()


@test_checker_decorator("ber_class_2_events",
                        INFO="Class II bit error events")
def test_ber_class_2_events(kwargs):
    return kwargs["CMD"].fetch_ber_class_2_events()


@test_checker_decorator("ber_class_2_ber",
                        INFO="Class II bit error rate (%)")
def test_ber_class_2_ber(kwargs):
    return kwargs["CMD"].fetch_ber_class_2_ber()


@test_checker_decorator("ber_class_2_rber",
                        INFO="Class II bit residual error rate (%)")
def test_ber_class_2_rber(kwargs):
    return kwargs["CMD"].fetch_ber_class_2_rber()


@test_checker_decorator("ber_erased_events",
                        INFO="Erased frame events")
def test_ber_erased_events(kwargs):
    return kwargs["CMD"].fetch_ber_erased_events()


@test_checker_decorator("ber_erased_fer",
                        INFO="Erased frame rate (%)")
def test_ber_erased_fer(kwargs):
    return kwargs["CMD"].fetch_ber_erased_fer()


@test_checker_decorator("ber_crc_errors",
                        INFO="CRC errors")
def test_ber_crc_errors(kwargs):
    return kwargs["CMD"].fetch_ber_crc_errors()

#
# Power calibration
#


UMSITE_TM3_VGA2_DEF = 22


@test_checker_decorator("power_vswr_vga2",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="Power&VSWR vs VGA2")
def test_power_vswr_vga2(kwargs):
    cmd = kwargs["CMD"]
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
    umtrx_vga2_def = kwargs["UMTRX_VGA2_DEF"] if \
        "UMTRX_VGA2_DEF" in kwargs else UMSITE_TM3_VGA2_DEF
    try:
        tr.output_progress("Testing power&VSWR vs VGA2")
        tr.output_progress("VGA2\tPk power\tAvg power\tVPF\tVPR")
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
        bts.umtrx_set_tx_vga2(chan, umtrx_vga2_def)


@test_checker_decorator("vswr_vga2",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="VSWR vs VGA2")
def test_vswr_vga2(kwargs):
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
    umtrx_vga2_def = kwargs["UMTRX_VGA2_DEF"] if \
        "UMTRX_VGA2_DEF" in kwargs else UMSITE_TM3_VGA2_DEF
    try:
        tr.output_progress("Testing VSWR vs VGA2")
        tr.output_progress("VGA2\tVPF\tVPR")
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
        bts.umtrx_set_tx_vga2(chan, umtrx_vga2_def)


@test_checker_decorator("power_vswr_dcdc",
                        DUT=["UmTRX", "UmSITE"],
                        INFO="Power&VSWR vs DCDC control")
def test_power_vswr_dcdc(kwargs):
    cmd = kwargs["CMD"]
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
    dut = kwargs["DUT_CHECKS"]
    try:
        tr.output_progress("Testing power&VSWR vs DCDC control")
        tr.output_progress("DCDC_R\tPk power\tAvg power\tVPF\tVPR")
        res = []
        for dcdc in range(dut["ddc_r_min"], dut["ddc_r_max"] + 1):
            bts.umtrx_set_dcdc_r(dcdc)
            power_pk = cmd.ask_peak_power()
            power_avg = cmd.ask_burst_power_avg()
            (vpf, vpr) = bts.umtrx_get_vswr_sensors(chan)
            res.append((dcdc, power_pk, power_avg, vpf, vpr))
            tr.output_progress("%d\t%.1f\t%.1f\t%.2f\t%.2f" % res[-1])
        # Sweep from max to min to weed out temperature dependency
        for dcdc in range(dut["ddc_r_max"], dut["ddc_r_min"] - 1, -1):
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


@test_checker_decorator("enable_tch_loopback",
                        INFO="Enabling BTS loopback mode")
def test_enable_tch_loopback(kwargs):
    kwargs["CMD"].switch_to_man_btch()
    return kwargs["BTS"].bts_en_loopback()


def cmd57_configure(cmd, arfcn):
    """ Configure the CMD57 """
    cmd.configure_man(ccch_arfcn=arfcn, tch_arfcn=arfcn,
                      tch_ts=2, tsc=7,
                      expected_power=37, tch_tx_power=-60,
                      tch_mode='PR16', tch_timing=0)
    cmd.configure_spectrum_modulation(burst_num=10)
    arfcnset = cmd.ask_bts_ccch_arfcn()
    # print("ARFCN=%d NET=%s" % (arfcnset, cmd.ask_network_type()))
    return arfcnset


@test_checker_decorator("configure_cmd57",
                        INFO="Configure CMD57 for using with the DUT",
                        CHECK=test_bool_checker())
def test_configure_cmd57(kwargs):
    cmd = kwargs["CMD"]
    arfcn = kwargs["ARFCN"]
    dut = kwargs["DUT"]
    kwargs["BTS"].bts_set_maxdly(10)

    if dut.startswith("UmTRX"):
        cmd.set_io_used('I1O2')
    else:
        cmd.set_io_used('I1O1')

    set_band_using_arfcn(cmd, arfcn)

    cmd.switch_to_man_bidl()
    return cmd57_configure(cmd, arfcn) == arfcn


@test_checker_decorator("run_tch_sync",
                        INFO="Syncronize CMD57 with the DUT",
                        CHECK=test_val_checker(TEST_OK))
def run_tch_sync(kwargs):
    # print("Starting Tx tests.")

    # Make sure we start in idle mode
    kwargs["CMD"].switch_to_idle()

    # Measure peak power before everything else
    res = test_burst_power_peak_wait(kwargs)

    # Prepare for TCH tests
    test_enable_tch_loopback(kwargs)
    return res


###############################
#   Main test run function
###############################


def run_bts_tests(kwargs):
    # print("Starting BTS tests.")

    # Stop osmo-trx to unlock UmTRX
    kwargs["BTS"].osmo_trx_stop()

    # Collect information about the BTS
    bts_read_uname(kwargs)
    bts_read_umtrx_serial(kwargs)

    umtrx_gps_time(kwargs)
    bts_hw_model(kwargs)
    bts_hw_band(kwargs)
    bts_umtrx_ver(kwargs)

    # Generate Test ID to be used in file names
    gen_test_id(kwargs)

    # Autocalibrate UmTRX
    test_id = str(kwargs["TR"].get_test_result("test_id", "system")[2])
    bts_umtrx_autocalibrate(kwargs["BTS"],
                            get_band(kwargs["ARFCN"]),
                            "out/calibration." + test_id + ".log",
                            "calibration.err." + test_id + ".log")

    # UmTRX Reset Test
    umtrx_reset_test(kwargs)

    # Start osmo-trx again
    kwargs["BTS"].osmo_trx_start()


def run_cmd57_info(kwargs):
    # print("Collecting CMD57 information.")

    # Collect useful information about the CMD57
    test_tester_id(kwargs)
    test_tester_options(kwargs)


def run_tx_tests(kwargs):
    # print("Starting Tx tests.")

    # Burst power measurements
    test_burst_power_avg(kwargs)
    test_burst_power_array(kwargs)

    # Phase and frequency measurements
    test_freq_error(kwargs)
    test_phase_err_array(kwargs)
    test_phase_err_pk(kwargs)  # fetches calculated value only
    test_phase_err_avg(kwargs)  # fetches calculated value only

    # Modulation spectrum measurements
    test_spectrum_modulation_offsets(kwargs)
    test_spectrum_modulation_tolerance_abs(kwargs)
    test_spectrum_modulation_tolerance_rel(kwargs)
    test_spectrum_modulation(kwargs)
    test_spectrum_modulation_match(kwargs)

    # Switching spectrum measurements
    test_spectrum_switching_offsets(kwargs)
    test_spectrum_switching_tolerance_abs(kwargs)
    test_spectrum_switching_tolerance_rel(kwargs)
    test_spectrum_switching(kwargs)
    test_spectrum_switching_match(kwargs)


def run_ber_tests(kwargs):
    cmd = kwargs["CMD"]
    # print("Starting BER tests.")

    test_ber_configure(kwargs)

    # BER test settings
    test_ber_used_ts_power(kwargs)
    test_ber_unused_ts_power(kwargs)
    test_ber_frames_num(kwargs)
    test_ber_max_test_time(kwargs)
    test_ber_abort_condition(kwargs)
    test_ber_holdoff_time(kwargs)
    test_ber_limit_class_1b(kwargs)
    test_ber_max_class_1b_samples(kwargs)
    test_ber_limit_class_2(kwargs)
    test_ber_max_class_2_samples(kwargs)
    test_ber_limit_erased_frames(kwargs)
    test_ber_max_erased_frames_samples(kwargs)

    # BER test result
    test_ber_test_result(kwargs)
    test_ber_class_1b_events(kwargs)
    test_ber_class_1b_ber(kwargs)
    test_ber_class_1b_rber(kwargs)
    test_ber_class_2_events(kwargs)
    test_ber_class_2_ber(kwargs)
    test_ber_class_2_rber(kwargs)
    test_ber_erased_events(kwargs)
    test_ber_erased_fer(kwargs)
    test_ber_crc_errors(kwargs)

    # Nice printout, just for the screen
    cmd.print_ber_test_settings()
    cmd.print_ber_test_result(False)


def get_band(arfcn):
    if 511 < arfcn < 886:
        return "DCS1800"
    elif (974 < arfcn < 1024) or arfcn == 0:
        return "EGSM900"
    elif 0 < arfcn < 125:
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
        print("This band isn't supported by CMD57")


def check_arfcn(n, band):
    if band == "GSM900":
        return 1 <= n <= 124
    elif band == "EGSM900":
        return (0 <= n <= 124) or (975 <= n <= 1023)
    elif band == "RGSM900":
        return (0 <= n <= 124) or (955 <= n <= 1023)
    elif band == "GSM1800" or band == "DCS1800":
        return 512 <= n <= 885
    else:
        return False


@test_checker_decorator("load_dut_checks",
                        INFO="Load DUT specific checks")
def load_dut_checks(kwargs):
    import bts_params
    dut = kwargs.get("DUT")
    tr = kwargs["TR"]

    if dut not in bts_params.HARDWARE_LIST.keys():
        tr.output_progress(("Unknown device %s!\n" % dut) +
                           ("Supported: %s" % str(
                               [i for i in bts_params.HARDWARE_LIST.keys()])))
        return None

    dut_checks = bts_params.HARDWARE_LIST[dut]
    kwargs["DUT_CHECKS"] = dut_checks
    return dut


@test_checker_decorator("check_hw_band",
                        INFO="Check whether DUT supports selected ARFCN",
                        CHECK=test_bool_checker())
def check_hw_band(kwargs):
    dut = kwargs["DUT"]
    arfcn = kwargs["ARFCN"]
    dut_checks = kwargs["DUT_CHECKS"]
    tr = kwargs["TR"]
    hw_band = dut_checks.get("hw_band")

    if hw_band is not None and not check_arfcn(arfcn, hw_band):
        tr.output_progress(("Hardware %s doesn't support ARFCN %d in band " +
                            "%s") % (dut, arfcn, dut_checks["hw_band"]))
        return False
    return True


@test_checker_decorator("connect_rf_to_cmd57",
                        INFO="UI interactions to reconnect CMD57",
                        CHECK=test_bool_checker())
def connect_rf_to_cmd57(kwargs):
    return kwargs["UI"].ask("Connect CMD57 to the TRX%s." %
                            str(kwargs.get("CHAN", "")))
