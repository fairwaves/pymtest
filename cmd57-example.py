#!/usr/bin/env python3 -i
import os
import sys
# Add the parent dir to search paths
# libs_dir = os.path.join(os.path.dirname(os.path.realpath( __file__ )), '..')
# if os.path.isdir(libs_dir):
#    sys.path.append(libs_dir)

from scpi.devices import cmd57_console as cmd57
import atexit

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -i cmd57-example.py /dev/ttyUSB0")
        sys.exit(1)
    # Then put to interactive mode
    os.environ['PYTHONINSPECT'] = '1'
    dev = cmd57.rs232(sys.argv[1], rtscts=True)
    atexit.register(dev.quit)

    # dev.configure_man(ccch_arfcn=75, tch_arfcn=75, tch_ts=0, tsc=7,
    #                   expected_power=37, tch_tx_power=-50,
    #                   tch_mode='LOOP', tch_timing=0)
    # dev.configure_mod(expected_power=37, arfcn=75, tsc=7,
    #                   decode='STANdard', input_bandwidth='NARRow',
    #                   trigger_mode='POWer')
    # dev.configure_spectrum_modulation_mask_rel(43)
    # most strict spectrum mask

    dev.print_sys_info()
    # dev.print_sys_config()
    dev.print_man_config()
    dev.print_mod_config()
    dev.print_cur_mode()

    print("")
    print("Expecting your input now")
