#!/usr/bin/env python

HARDWARE_LIST = {
    "UmSITE-TM10-1800": {
        "hw_model": "UmSITE-TM10",
        "burst_power_peak_min": 37,  # dBm
        "burst_power_peak_max": 39.5,  # dBm
        "burst_power_avg_min": 37,  # dBm
        "burst_power_avg_max": 39.5,  # dBm
        "freq_error": 50,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 2.5,  # deg
        "ddc_r_min": 128,
        "ddc_r_max": 255,
        "ddc_r_def": 255,
        "hw_band": "DCS1800"
    },
    "UmSITE-TM10-E900": {
        "hw_model": "UmSITE-TM10",
        "burst_power_peak_min": 39,  # dBm
        "burst_power_peak_max": 42,  # dBm
        "burst_power_avg_min": 39,  # dBm
        "burst_power_avg_max": 42,  # dBm
        "freq_error": 50,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 2.0,  # deg
        "ddc_r_min": 128,
        "ddc_r_max": 255,
        "ddc_r_def": 255,
        "hw_band": "EGSM900"
    },
    "UmSITE-TM3-any": {
        "hw_model": "UmSITE-TM3",
        "burst_power_peak_min": 34,  # dBm
        "burst_power_peak_max": 36,  # dBm
        "burst_power_avg_min": 34,  # dBm
        "burst_power_avg_max": 36,  # dBm
        "freq_error": 50,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 2.0,  # deg
        "ddc_r_min": 128,
        "ddc_r_max": 230,
        "ddc_r_def": 215,
        "hw_band": None
    },
    "UmTRX-v2.3.1": {
        "hw_model": "UmTRX",
        "burst_power_peak_min": 5,  # dBm
        "burst_power_peak_max": 24,  # dBm
        "burst_power_avg_min": 5,  # dBm
        "burst_power_avg_max": 24,  # dBm
        "freq_error": 50,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 2.0,  # deg
        "ddc_r_min": 0,
        "ddc_r_max": 0,
        "ddc_r_def": 0,
        "hw_band": None,
        "ber_used_ts_power": -80,
        "ber_test_num": 3
    },
    "UmTRX-v2.2": {
        "hw_model": "UmTRX-2.2",
        "burst_power_peak_min": 15,  # dBm
        "burst_power_peak_max": 17,  # dBm
        "burst_power_avg_min": 14,  # dBm
        "burst_power_avg_max": 17,  # dBm
        "freq_error": 50,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 3.0,  # deg
        "ddc_r_min": 0,
        "ddc_r_max": 0,
        "ddc_r_def": 0,
        "hw_band": None,
        "ber_used_ts_power": -80,
        "ber_test_num": 3
    },
    "OC": {
        "login": "opencellular",
        "password": "123",
        "hw_model": "OC",
        "burst_power_peak_min": 31,  # dBm
        "burst_power_peak_max": 34,  # dBm
        "burst_power_avg_min": 30,  # dBm
        "burst_power_avg_max": 33,  # dBm
        "freq_error": 200,  # Hz
        "phase_err_pk_min": -10.0,  # deg
        "phase_err_pk_max": 10.0,  # deg
        "phase_err_avg_min": 0.5,  # deg
        "phase_err_avg_max": 3.0,  # deg
        "ddc_r_min": 0,
        "ddc_r_max": 0,
        "ddc_r_def": 0,
        "hw_band": None,
        "ber_unused_ts_power": -20,
        "ber_used_ts_power": -70
    }
}
