#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fwtp_core import *
import time



###############################
#   non-CMD57 based tests
###############################

@test_checker_decorator("bts_hw_model",
                        INFO="BTS hardware model",
                        CHECK=test_substr_checker(evaluate_dut_check("hw_model")))
def bts_hw_model(**kwargs):
    return kwargs["BTS"].bts_get_hw_config('HW_MODEL')[0].strip('\n')

@test_checker_decorator("bts_hw_band",
                        INFO="BTS hardware band")
def bts_hw_band(**kwargs):
    return kwargs["BTS"].bts_get_hw_config('BAND')[0].strip('\n')

@test_checker_decorator("bts_umtrx_ver",
                        DUT=["UmTRX","UmSITE"],
                        INFO="BTS umtrx ver")
def bts_umtrx_ver(**kwargs):
    return kwargs["BTS"].bts_get_hw_config('UMTRX_VER')[0].strip('\n')

@test_checker_decorator("umtrx_reset_test",
                        DUT=["UmTRX","UmSITE"],
                        INFO="UmTRX Reset and Safe firmware loading test",
                        CHECK=test_bool_checker())
def umtrx_reset_test(**kwargs):
    lns = kwargs["BTS"].umtrx_reset_test()
    kwargs["TR"].output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1

@test_checker_decorator("umtrx_gps_time",
                        DUT=["UmTRX","UmSITE"],
                        INFO="UmTRX GPS time",
                        CHECK=test_bool_checker())
def umtrx_gps_time(**kwargs):
    lns = kwargs["BTS"].umtrx_get_gps_time()
    kwargs["TR"].output_progress(str(lns))
    return len(lns) > 0 and lns[-1].find('SUCCESS') != -1


@test_checker_decorator("bts_uname",
                        INFO="BTS system information")
def bts_read_uname(**kwargs):
    return kwargs["BTS"].get_uname()


@test_checker_decorator("umtrx_serial",
                        DUT=["UmTRX","UmSITE"],
                        INFO="UmTRX serial number")
def bts_read_umtrx_serial(**kwargs):
    return kwargs["BTS"].get_umtrx_eeprom_val("serial")


@test_checker_decorator("test_id")
def gen_test_id(**kwargs):
    ''' Generates a unique test ID '''
    tr = kwargs["TR"]
    uname_res = tr.get_test_result("bts_uname", "system")
    serial_res =  tr.get_test_result("umtrx_serial", "system")
    if uname_res[1] != TEST_OK or serial_res[1] != TEST_OK:
        return None
    name = uname_res[2].split()[1]
    timestr = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(time.time()))
    fixed_test_id = name+'_'+serial_res[2]
    tr.load_prev_data(fixed_test_id)
    return fixed_test_id+'_'+timestr

@test_checker_decorator("test_id2")
def gen_test_id2(**kwargs):
    ''' Generates a unique test ID '''
    tr = kwargs["TR"]
    uname_res = tr.get_test_result("/", TestSuiteConfig.KNOWN_TESTS_DESC["bts_uname"], "system")
    print (uname_res)
    if uname_res[1] != TEST_OK:
        return None
    name = uname_res[2].split()[1]
    timestr = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(time.time()))
    fixed_test_id = name
    tr.load_prev_data(fixed_test_id)
    return fixed_test_id+'_'+timestr

@test_checker_decorator("umtrx_autocalibrate",
                        DUT=["UmTRX","UmSITE"],
                        INFO="UmTRX autocalibration",
                        CHECK=test_bool_checker())
def bts_umtrx_autocalibrate(bts, preset, filename_stdout, filename_stderr):
    return bts.umtrx_autocalibrate(preset, filename_stdout, filename_stderr)



###############################
#   CMD57 based tests
###############################


@test_checker_decorator("tester_name",
                        INFO="Tester device name")
def test_tester_id(**kwargs):
    id_str = kwargs["CMD"].identify()
    name = id_str[0]+' '+id_str[1]
    return name

@test_checker_decorator("tester_serial",
                        INFO="Tester serial")
def test_tester_id(**kwargs):
    id_str = kwargs["CMD"].identify()
    return id_str[2]

@test_checker_decorator("tester_version",
                        INFO="Tester veersion")
def test_tester_id(**kwargs):
    id_str = kwargs["CMD"].identify()
    return id_str[3]

@test_checker_decorator("tester_options",
                        INFO="Tester installed options")
def test_tester_options(**kwargs):
    return " ".join(kwargs["CMD"].ask_installed_options())


@test_checker_decorator("burst_power_peak",
                        INFO="TRX output power (dBm)",
                        CHECK=test_minmax_checker(
                                evaluate_dut_check("burst_power_peak_min"),
                                evaluate_dut_check("burst_power_peak_max")))
def test_burst_power_peak(**kwargs):
    ''' Check output power level '''
    return kwargs["CMD"].ask_peak_power()

@test_checker_decorator("burst_power_peak_wait",
                        INFO="Wait for TRX output power (dBm)",
                        CHECK=test_val_checker(TEST_OK))
def test_burst_power_peak_wait(**kwargs):
    ''' Wait for output power level '''
    timeout = kwargs["TIMEOUT"] if "TIMEOUT" in kwargs else 20
    res = TEST_NA
    t = time.time()
    while res != TEST_OK and time.time()-t < timeout:
        res = test_burst_power_peak(**kwargs)
        if res == TEST_ABORTED:
            return res
    res = test_burst_power_peak(**kwargs)
    return res


@test_checker_decorator("bcch_presence",
                        INFO="BCCH detected",
                        CHECK=test_bool_checker())
def test_bcch_presence(**kwargs):
    ''' Check BCCH presence '''
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
def test_burst_power_avg(**kwargs):
    return kwargs["CMD"].ask_burst_power_avg()


@test_checker_decorator("burst_power_array",
                        INFO="Burst power array (dBm)")
def test_burst_power_array(**kwargs):
    return kwargs["CMD"].ask_burst_power_arr()


@test_checker_decorator("freq_error",
                        INFO="Frequency error (Hz)",
                        CHECK=test_abs_checker(evaluate_dut_check("freq_error")))
def test_freq_error(**kwargs):
    return kwargs["CMD"].ask_freq_err()


@test_checker_decorator("phase_err_array",
                        INFO="Phase error array (deg)")
def test_phase_err_array(**kwargs):
    return kwargs["CMD"].ask_phase_err_arr()


@test_checker_decorator("phase_err_pk",
                        INFO="Phase error peak (deg)",
                        CHECK=test_minmax_checker(
                                evaluate_dut_check("phase_err_pk_min"),
                                evaluate_dut_check("phase_err_pk_max")))
def test_phase_err_pk(**kwargs):
    return kwargs["CMD"].fetch_phase_err_pk()


@test_checker_decorator("phase_err_avg",
                        INFO="Phase error avg (deg)",
                        CHECK=test_minmax_checker(
                                evaluate_dut_check("phase_err_avg_min"),
                                evaluate_dut_check("phase_err_avg_max")))
def test_phase_err_avg(**kwargs):
    return kwargs["CMD"].fetch_phase_err_rms()

#
# Spectrum tests
#


@test_checker_decorator("spectrum_modulation_offsets",
                        INFO="Modulation spectrum measurement offsets (kHz)")
def test_spectrum_modulation_offsets(**kwargs):
    return kwargs["CMD"].fetch_spectrum_modulation_offsets()


@test_checker_decorator("spectrum_modulation_tolerance_abs",
                        INFO="Modulation spectrum absolute tolerance mask (dBm)")
def test_spectrum_modulation_tolerance_abs(**kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_tolerance_abs()


@test_checker_decorator("spectrum_modulation_tolerance_rel",
                        INFO="Modulation spectrum relative tolerance mask (dBc)")
def test_spectrum_modulation_tolerance_rel(**kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_tolerance_rel()


@test_checker_decorator("spectrum_modulation",
                        INFO="Modulation spectrum measured (dBc)")
def test_spectrum_modulation(**kwargs):
    return kwargs["CMD"].ask_spectrum_modulation()


@test_checker_decorator("spectrum_modulation_match",
                        INFO="Modulation spectrum match",
                        CHECK=test_val_checker("MATC"))
def test_spectrum_modulation_match(**kwargs):
    return kwargs["CMD"].ask_spectrum_modulation_match()


@test_checker_decorator("spectrum_switching_offsets",
                        INFO="Switching spectrum measurement offsets (kHz)")
def test_spectrum_switching_offsets(**kwargs):
    return kwargs["CMD"].fetch_spectrum_switching_offsets()


@test_checker_decorator("spectrum_switching_tolerance_abs",
                        INFO="Switching spectrum absolute tolerance mask (dBm)")
def test_spectrum_switching_tolerance_abs(**kwargs):
    return kwargs["CMD"].ask_spectrum_switching_tolerance_abs()


@test_checker_decorator("spectrum_switching_tolerance_rel",
                        INFO="Switching spectrum relative tolerance mask (dBc)")
def test_spectrum_switching_tolerance_rel(**kwargs):
    return kwargs["CMD"].ask_spectrum_switching_tolerance_rel()


@test_checker_decorator("spectrum_switching",
                        INFO="Switching spectrum measured (dBc)")
def test_spectrum_switching(**kwargs):
    return kwargs["CMD"].ask_spectrum_switching()


@test_checker_decorator("spectrum_switching_match",
                        INFO="Switching spectrum match")
def test_spectrum_switching_match(**kwargs):
    return kwargs["CMD"].ask_spectrum_switching_match()

#
# BER test settings
#


@test_checker_decorator("ber_configure",
                        INFO="BER test configuration",
                        CHECK=test_ignore_checker())
def test_ber_configure(**kwargs):
    cmd = kwargs["CMD"]
    dut = kwargs["DUT"]
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

    ber_test_num = dut_checks["ber_test_num"] if "ber_test_num" in dut_checks else 1
    return cmd.set_ber_test_num(ber_test_num)


@test_checker_decorator("ber_used_ts_power",
                        INFO="Used TS power (dBm)")
def test_ber_used_ts_power(**kwargs):
    return kwargs["CMD"].ask_ber_used_ts_power()


@test_checker_decorator("ber_unused_ts_power",
                        INFO="Unused TS power (dBm)")
def test_ber_unused_ts_power(**kwargs):
    return kwargs["CMD"].ask_ber_unused_ts_power()


@test_checker_decorator("ber_frames_num",
                        INFO="Frames to send")
def test_ber_frames_num(**kwargs):
    return kwargs["CMD"].ask_ber_frames_num()


@test_checker_decorator("ber_max_test_time",
                        INFO="Test time")
def test_ber_max_test_time(**kwargs):
    return kwargs["CMD"].ask_ber_max_test_time()


@test_checker_decorator("ber_abort_condition",
                        INFO="Abort condition")
def test_ber_abort_condition(**kwargs):
    return kwargs["CMD"].ask_ber_abort_cond()


@test_checker_decorator("ber_holdoff_time",
                        INFO="Hold-off time")
def test_ber_holdoff_time(**kwargs):
    return kwargs["CMD"].ask_ber_holdoff_time()


@test_checker_decorator("ber_limit_class_1b",
                        INFO="Class Ib bit errors tolerance (%)")
def test_ber_limit_class_1b(**kwargs):
    return kwargs["CMD"].ask_ber_limit_class_1b()


@test_checker_decorator("ber_max_class_1b_samples",
                        INFO="Class Ib bit errors max number")
def test_ber_max_class_1b_samples(**kwargs):
    return kwargs["CMD"].ask_ber_max_class_1b_samples()


@test_checker_decorator("ber_limit_class_2",
                        INFO="Class II bit errors tolerance (%)")
def test_ber_limit_class_2(**kwargs):
    return kwargs["CMD"].ask_ber_limit_class_2()


@test_checker_decorator("ber_max_class_2_samples",
                        INFO="Class II bit errors max number")
def test_ber_max_class_2_samples(**kwargs):
    return kwargs["CMD"].ask_ber_max_class_2_samples()


@test_checker_decorator("ber_limit_erased_frames",
                        INFO="Erased frames tolerance (%)")
def test_ber_limit_erased_frames(**kwargs):
    return kwargs["CMD"].ask_ber_limit_erased_frames()


@test_checker_decorator("ber_max_erased_frames_samples",
                        INFO="Erased frames max number")
def test_ber_max_erased_frames_samples(**kwargs):
    return kwargs["CMD"].ask_ber_max_erased_frames_samples()

#
# BER test results
#


@test_checker_decorator("ber_test_result",
                        INFO="BER test result",
                        CHECK=test_val_checker("PASS"))
def test_ber_test_result(**kwargs):
    return kwargs["CMD"].read_ber_test_result()


@test_checker_decorator("ber_class_1b_events",
                        INFO="Class Ib bit error events")
def test_ber_class_1b_events(**kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_events()


@test_checker_decorator("ber_class_1b_ber",
                        INFO="Class Ib bit error rate (%)")
def test_ber_class_1b_ber(**kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_ber()


@test_checker_decorator("ber_class_1b_rber",
                        INFO="Class Ib bit residual error rate (%)")
def test_ber_class_1b_rber(**kwargs):
    return kwargs["CMD"].fetch_ber_class_1b_rber()


@test_checker_decorator("ber_class_2_events",
                        INFO="Class II bit error events")
def test_ber_class_2_events(**kwargs):
    return kwargs["CMD"].fetch_ber_class_2_events()


@test_checker_decorator("ber_class_2_ber",
                        INFO="Class II bit error rate (%)")
def test_ber_class_2_ber(**kwargs):
    return kwargs["CMD"].fetch_ber_class_2_ber()


@test_checker_decorator("ber_class_2_rber",
                        INFO="Class II bit residual error rate (%)")
def test_ber_class_2_rber(**kwargs):
    return kwargs["CMD"].fetch_ber_class_2_rber()


@test_checker_decorator("ber_erased_events",
                        INFO="Erased frame events")
def test_ber_erased_events(**kwargs):
    return kwargs["CMD"].fetch_ber_erased_events()


@test_checker_decorator("ber_erased_fer",
                        INFO="Erased frame rate (%)")
def test_ber_erased_fer(**kwargs):
    return kwargs["CMD"].fetch_ber_erased_fer()


@test_checker_decorator("ber_crc_errors",
                        INFO="CRC errors")
def test_ber_crc_errors(**kwargs):
    return kwargs["CMD"].fetch_ber_crc_errors()

#
# Power calibration
#


@test_checker_decorator("power_vswr_vga2",
                        DUT=["UmTRX","UmSITE"],
                        INFO="Power&VSWR vs VGA2")
def test_power_vswr_vga2(**kwargs):
    cmd = kwargs["CMD"]
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
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


@test_checker_decorator("vswr_vga2",
                        DUT=["UmTRX","UmSITE"],
                        INFO="VSWR vs VGA2")
def test_vswr_vga2(**kwargs):
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
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


@test_checker_decorator("power_vswr_dcdc",
                        DUT=["UmTRX","UmSITE"],
                        INFO="Power&VSWR vs DCDC control")
def test_power_vswr_dcdc(**kwargs):
    cmd = kwargs["CMD"]
    bts = kwargs["BTS"]
    chan = kwargs["CHAN"]
    tr = kwargs["TR"]
    dut = kwargs["DUT_CHECKS"]
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


@test_checker_decorator("enable_tch_loopback",
                        INFO="Enabling BTS loopback mode")
def test_enable_tch_loopback(**kwargs):
    kwargs["CMD"].switch_to_man_btch()
    return kwargs["BTS"].bts_en_loopback()



def cmd57_configure(cmd, arfcn):
    ''' Configure the CMD57 '''
    cmd.configure_man(ccch_arfcn=arfcn, tch_arfcn=arfcn,
                      tch_ts=2, tsc=7,
                      expected_power=37, tch_tx_power=-60,
                      tch_mode='PR16', tch_timing=0)
    cmd.configure_spectrum_modulation(burst_num=10)
    arfcnset = cmd.ask_bts_ccch_arfcn()
    print ("ARFCN=%d NET=%s" % (arfcnset, cmd.ask_network_type()))
    return arfcnset


@test_checker_decorator("configure_cmd57",
                        INFO="Configure CMD57 for using with the DUT",
                        CHECK=test_bool_checker())
def test_configure_cmd57(**kwargs):
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
def run_tch_sync(**kwargs):
    print("Starting Tx tests.")

    # Make sure we start in idle mode
    kwargs["CMD"].switch_to_idle()

    # Measure peak power before everything else
    res = test_burst_power_peak_wait(**kwargs)

    # Prepare for TCH tests
    test_enable_tch_loopback(**kwargs)
    return res


###############################
#   Main test run function
###############################


def run_bts_tests(**kwargs):
    print("Starting BTS tests.")

    # Stop osmo-trx to unlock UmTRX
    kwargs["BTS"].osmo_trx_stop()

    # Collect information about the BTS
    bts_read_uname(**kwargs)
    bts_read_umtrx_serial(**kwargs)

    umtrx_gps_time(**kwargs)
    bts_hw_model(**kwargs)
    bts_hw_band(**kwargs)
    bts_umtrx_ver(**kwargs)

    # Generate Test ID to be used in file names
    gen_test_id(**kwargs)

    # Autocalibrate UmTRX
    test_id = str(tr.get_test_result("test_id", "system")[2])
    bts_umtrx_autocalibrate(kwargs["BTS"], kwargs["BAND"], "out/calibration."+test_id+".log", "calibration.err."+test_id+".log")

    # UmTRX Reset Test
    umtrx_reset_test(**kwargs)

    # Start osmo-trx again
    kwargs["BTS"].osmo_trx_start()


def run_cmd57_info(**kwargs):
    print("Collecting CMD57 information.")

    # Collect useful information about the CMD57
    test_tester_id(**kwargs)
    test_tester_options(**kwargs)



def run_tx_tests(**kwargs):
    print("Starting Tx tests.")

    # Burst power measurements
    test_burst_power_avg(**kwargs)
    test_burst_power_array(**kwargs)

    # Phase and frequency measurements
    test_freq_error(**kwargs)
    test_phase_err_array(**kwargs)
    test_phase_err_pk(**kwargs)  # fetches calculated value only
    test_phase_err_avg(**kwargs)  # fetches calculated value only

    # Modulation spectrum measurements
    test_spectrum_modulation_offsets(**kwargs)
    test_spectrum_modulation_tolerance_abs(**kwargs)
    test_spectrum_modulation_tolerance_rel(**kwargs)
    test_spectrum_modulation(**kwargs)
    test_spectrum_modulation_match(**kwargs)

    # Switching spectrum measurements
    test_spectrum_switching_offsets(**kwargs)
    test_spectrum_switching_tolerance_abs(**kwargs)
    test_spectrum_switching_tolerance_rel(**kwargs)
    test_spectrum_switching(**kwargs)
    test_spectrum_switching_match(**kwargs)


def run_ber_tests(**kwargs):
    print("Starting BER tests.")

    test_ber_configure(**kwargs)

    # BER test settings
    test_ber_used_ts_power(**kwargs)
    test_ber_unused_ts_power(**kwargs)
    test_ber_frames_num(**kwargs)
    test_ber_max_test_time(**kwargs)
    test_ber_abort_condition(**kwargs)
    test_ber_holdoff_time(**kwargs)
    test_ber_limit_class_1b(**kwargs)
    test_ber_max_class_1b_samples(**kwargs)
    test_ber_limit_class_2(**kwargs)
    test_ber_max_class_2_samples(**kwargs)
    test_ber_limit_erased_frames(**kwargs)
    test_ber_max_erased_frames_samples(**kwargs)

    # BER test result
    test_ber_test_result(**kwargs)
    test_ber_class_1b_events(**kwargs)
    test_ber_class_1b_ber(**kwargs)
    test_ber_class_1b_rber(**kwargs)
    test_ber_class_2_events(**kwargs)
    test_ber_class_2_ber(**kwargs)
    test_ber_class_2_rber(**kwargs)
    test_ber_erased_events(**kwargs)
    test_ber_erased_fer(**kwargs)
    test_ber_crc_errors(**kwargs)

    # Nice printout, just for the screen
    cmd.print_ber_test_settings()
    cmd.print_ber_test_result(False)



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




