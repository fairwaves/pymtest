#!/usr/bin/env python
#
# Copyright 2017 Alexander Chemeris <Alexander.Chemeris@fairwaves.co>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import socket, argparse, time
import umtrx_ctrl

GPSDO_CLOCK_FREQ = 52000000 # Hz
MEASUREMENT_DELAY = 1 # sec
MEASUREMENTS_TO_SUCCESS = 5      # in sec (roughly)
MEASUREMENTS_TO_TIMEOUT = 10*60  # in sec (roughly)

def gpsdo_wait(umtrx_vcxo_dev, tolerance=1, gpsdo_clock=GPSDO_CLOCK_FREQ,
               measurements_to_success=MEASUREMENTS_TO_SUCCESS, measurements_to_timeout=MEASUREMENTS_TO_TIMEOUT):
    measurements = 0
    successful_measurements = 0
    while True:
        # We're using unfiltered frequency
        freq = umtrx_vcxo_dev.get_gpsdo_freq()
        print("Iteration %d [successful %d] frequency %d" % (measurements, successful_measurements, freq))
        measurements += 1
        # Check whether we're within the tolerance range
        if freq <= gpsdo_clock+tolerance and freq >= gpsdo_clock-tolerance:
            successful_measurements += 1
        else:
            successful_measurements = 0
        # Are we stable?
        if successful_measurements >= measurements_to_success:
            return True
        # Or are we timing out?
        if measurements > measurements_to_timeout:
            return False
        # GPSDO measurments are updated once a second
        time.sleep(MEASUREMENT_DELAY)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Wait for UmTRX GPSDO to stabilize frequency.',
        epilog = "UmTRX is detected via broadcast unless explicit address is specified via --umtrx-addr option. 'None' returned while reading\writing indicates error in the process.")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    basic_opt = parser.add_mutually_exclusive_group()
    basic_opt.add_argument('--detect', dest = 'bcast_addr', default = '192.168.10.255',
                           help='broadcast domain where UmTRX should be discovered (default: 192.168.10.255)')
    basic_opt.add_argument('--umtrx-addr', dest = 'umtrx', const = '192.168.10.2', nargs='?',
                           help = 'UmTRX address (default: 192.168.10.2)')

    parser.add_argument('-t', '--tolerance', dest = 'tolerance', default=1, type = int,
                        help = 'Frequency tolerance in Hz relative to 52MHz UmTRX clock to consider GPSDO stable [default: 1]')

    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(umtrx_ctrl.UDP_TIMEOUT)
    umtrx = umtrx_ctrl.detect(sock, args.umtrx if args.umtrx is not None else args.bcast_addr)

    if umtrx is not None: # UmTRX address established
        if umtrx_ctrl.ping(sock, umtrx): # UmTRX probed
            print('UmTRX detected at %s' % umtrx)
            umtrx_vcxo_dev = umtrx_ctrl.umtrx_vcxo_dac(sock, umtrx)
            if gpsdo_wait(umtrx_vcxo_dev, args.tolerance):
                print("SUCCESS")
            else:
                print("TIMEOUT")
        else:
            print('UmTRX at %s is not responding.' % umtrx)
    else:
        print('No UmTRX detected over %s' % args.bcast_addr)
