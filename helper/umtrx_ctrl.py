#!/usr/bin/env python
#
# Copyright 2012 Fairwaves
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
import struct, socket
# pylint: disable = C0301, C0103, C0111, R0903, R0913

UDP_CONTROL_PORT = 49152
UDP_MAX_XFER_BYTES = 1024
UDP_TIMEOUT = 1
UDP_POLL_INTERVAL = 0.10 #in seconds
USRP2_CONTROL_PROTO_VERSION = 11 # Must match firmware proto. We're setting it in detect()
supported_control_proto_versions = [11, 12]

# see fw_common.h
CONTROL_FMT = '!LLL24x'
CONTROL_IP_FMT = '!LLLL20x'
SPI_FMT = '!LLLLLBBBB12x'
ZPU_ACTION_FMT = '!LLLLL16x'

n2xx_revs = {
  0x0a00: ["n200_r3", "n200_r2"],
  0x0a10: ["n200_r4"],
  0x0a01: ["n210_r3", "n210_r2"],
  0x0a11: ["n210_r4"],
  0xfa00: ["umtrx"],
  }

# remember kids: drugs are bad...
USRP2_CTRL_ID_HUH_WHAT = ord(' ')
USRP2_CTRL_ID_WAZZUP_BRO = ord('a')
USRP2_CTRL_ID_WAZZUP_DUDE = ord('A')
UMTRX_CTRL_ID_REQUEST = ord('u')
UMTRX_CTRL_ID_RESPONSE = ord('U')
USRP2_CTRL_ID_TRANSACT_ME_SOME_SPI_BRO = ord('s')
USRP2_CTRL_ID_OMG_TRANSACTED_SPI_DUDE = ord('S')
USRP2_CTRL_ID_DO_AN_I2C_READ_FOR_ME_BRO = ord('i')
USRP2_CTRL_ID_HERES_THE_I2C_DATA_DUDE = ord('I')
USRP2_CTRL_ID_WRITE_THESE_I2C_VALUES_BRO = ord('h')
USRP2_CTRL_ID_COOL_IM_DONE_I2C_WRITE_DUDE = ord('H')
USRP2_CTRL_ID_GET_THIS_REGISTER_FOR_ME_BRO = ord('r')
USRP2_CTRL_ID_OMG_GOT_REGISTER_SO_BAD_DUDE = ord('R')
USRP2_CTRL_ID_HOLLER_AT_ME_BRO = ord('l')
USRP2_CTRL_ID_HOLLER_BACK_DUDE = ord('L')
UMTRX_CTRL_ID_ZPU_REQUEST  = ord('z')
UMTRX_CTRL_ID_ZPU_RESPONSE = ord('Z')
USRP2_CTRL_ID_PEACE_OUT = ord('~')
SPI_EDGE_RISE = ord('r')
SPI_EDGE_FALL = ord('f')
UMTRX_ZPU_REQUEST_GET_VCTCXO_DAC = 1
UMTRX_ZPU_REQUEST_SET_VCTCXO_DAC = 2

def unpack_format(_str, fmt):
    return struct.unpack(fmt, _str)

def pack_control_fmt(proto_ver, pktid, seq):
    return struct.pack(CONTROL_FMT, proto_ver, pktid, seq)

def pack_spi_fmt(proto_ver, pktid, seq, dev, data, miso, mosi, bits, read):
    return struct.pack(SPI_FMT, proto_ver, pktid, seq, dev, data, miso, mosi, bits, read)

def pack_zpu_action_fmt(proto_ver, pktid, seq, action, data):
    return struct.pack(ZPU_ACTION_FMT, proto_ver, pktid, seq, action, data)

def recv_item(skt, fmt, chk, ind):
    try:
        pkt = skt.recv(UDP_MAX_XFER_BYTES)
        pkt_list = unpack_format(pkt, fmt)
#        print("Received %d bytes: %x, '%c', %x" % (len(pkt), pkt_list[0], pkt_list[1], pkt_list[2]))
        if pkt_list[1] != chk:
            return (None,None)
        return (pkt_list[ind],pkt_list[0])
    except socket.timeout:
        return (None,None)

def ping(skt, addr):
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    out_pkt = pack_control_fmt(USRP2_CONTROL_PROTO_VERSION, UMTRX_CTRL_ID_REQUEST, 0)
    skt.sendto(out_pkt, (addr, UDP_CONTROL_PORT))
    return recv_item(skt, CONTROL_FMT, UMTRX_CTRL_ID_RESPONSE, 1)

def detect(skt, bcast_addr):
    global USRP2_CONTROL_PROTO_VERSION
#    print('Detecting UmTRX over %s:' % bcast_addr)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)    
    out_pkt = pack_control_fmt(USRP2_CONTROL_PROTO_VERSION, UMTRX_CTRL_ID_REQUEST, 0)
#    print(" Sending %d bytes: %x, '%c',.." % (len(out_pkt), USRP2_CONTROL_PROTO_VERSION, UMTRX_CTRL_ID_REQUEST))
    skt.sendto(out_pkt, (bcast_addr, UDP_CONTROL_PORT))
    response,version = recv_item(skt, CONTROL_IP_FMT, UMTRX_CTRL_ID_RESPONSE, 3)
    if version is None or response is None:
        return None
    if not version in supported_control_proto_versions:
        print("Error: You Firmware is too old! Your protocol ver: %d. Protocol ver required: [%s]\n"
              % (version, ", ".join([str(x) for x in supported_control_proto_versions])))
    # If we support this version - use it
    USRP2_CONTROL_PROTO_VERSION = version
    return socket.inet_ntoa(struct.pack("<L", socket.ntohl(response)))

class umtrx_dev_spi:
    """ A class for talking to a device sitting on the SPI bus of UmTRX """

    def __init__(self, umtrx_socket, net_address, spi_bus_number, out_edge=SPI_EDGE_RISE, in_edge=SPI_EDGE_RISE):
        """ spi_bus_number - a number of SPI bus to read/write """
        self.skt = umtrx_socket
        self.addr = net_address
        self.spi_num = spi_bus_number
        self.out_edge = out_edge
        self.in_edge = in_edge

    def spi_rw(self, data, num_bits, readback):
        """ Write data to SPI bus and optionally read some data back.
        data - data to write to the SPI bus
        num_bits - number of bits of data to read/write
        readback - 1 to read data from SPI bus, 0 to ignore data on the bus """
        self.skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 0)
        out_pkt = pack_spi_fmt(USRP2_CONTROL_PROTO_VERSION, USRP2_CTRL_ID_TRANSACT_ME_SOME_SPI_BRO, \
                               0, self.spi_num, data, self.in_edge, self.out_edge, num_bits, readback)
        self.skt.sendto(out_pkt, (self.addr, UDP_CONTROL_PORT))
        ret,_ = recv_item(self.skt, SPI_FMT, USRP2_CTRL_ID_OMG_TRANSACTED_SPI_DUDE, 4) 
        return ret

class umtrx_lms_device:

    def __init__(self, umtrx_socket, net_address, lms_number):
        self.spi = umtrx_dev_spi(umtrx_socket, net_address, lms_number)
        self.verbosity = 0

    def reg_read(self, reg):
        data = self.spi.spi_rw(reg << 8, 16, 1) & ((1<<8)-1)
        if self.verbosity > 0: print("REG READ  0x%x -> 0x%x" % (reg, data,))
        return data

    def reg_write(self, reg, data):
        if self.verbosity > 0: print("REG WRITE 0x%x <- 0x%x" % (reg, data,))
        self.spi.spi_rw(((0x80 | reg) << 8) | data, 16, 0)

    def reg_rmw(self, reg, action):
        """ Read-Modify-Write for LMS register.
        'action' is a lambda(x) expression """
        reg_save = self.reg_read(reg)
        reg_val = action(reg_save)
        self.reg_write(reg, reg_val)
        return reg_save

    def reg_set_bits(self, reg, mask):
        return self.reg_rmw(reg, lambda x: x | int(mask))

    def reg_clear_bits(self, reg, mask):
        return self.reg_rmw(reg, lambda x: x & ~int(mask))

    def reg_write_bits(self, reg, mask, data):
        return self.reg_rmw(reg, lambda x: (x & ~int(mask)) | int(data))

    def reg_get_bits(self, reg, mask, shift):
        return (self.reg_read(reg)&int(mask)) >> shift

class umtrx_vcxo_dac:

    def __init__(self, umtrx_socket, net_address):
        self.skt = umtrx_socket
        self.addr = net_address
#        self.spi = umtrx_dev_spi(umtrx_socket, net_address, 4, out_edge=SPI_EDGE_FALL)

    def zpu_action(self, action, data=0):
        self.skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 0)
        out_pkt = pack_zpu_action_fmt(USRP2_CONTROL_PROTO_VERSION, UMTRX_CTRL_ID_ZPU_REQUEST, \
                                      0, action, data)
        self.skt.sendto(out_pkt, (self.addr, UDP_CONTROL_PORT))
        ret,_ = recv_item(self.skt, ZPU_ACTION_FMT, UMTRX_CTRL_ID_ZPU_RESPONSE, 4)
        return ret

    def set_dac(self, v):
        self.zpu_action(UMTRX_ZPU_REQUEST_SET_VCTCXO_DAC, v)

    def get_dac(self):
        return self.zpu_action(UMTRX_ZPU_REQUEST_GET_VCTCXO_DAC)

def create_umtrx_lms_device(lms_number, ip_address=None, bcast_addr="192.168.10.255"):
    ''' Fabric function to create UmTRX LMS device class '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)
    umtrx_addr = detect(sock, ip_address if ip_address is not None else bcast_addr)
    umtrx_lms_dev = None
    if umtrx_addr is not None: # UmTRX address established
        if ping(sock, umtrx_addr): # UmTRX probed
            umtrx_lms_dev = umtrx_lms_device(sock, umtrx_addr, lms_number)
    return umtrx_lms_dev
