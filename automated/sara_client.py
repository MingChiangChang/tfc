"""
Sara socket communication class.
Contains the python client side to operate the cameras,
spectrometer, the LasGo stage, and, at some point, 
the XRD devices from python.
"""
from crccheck.crc import Crc32, CrcXmodem
from crccheck.checksum import Checksum32

import logging
import logging.config
import yaml
import zlib
import binascii
import socket
import struct
import sys
import io
import time
import numpy as np
import copy as cp
import imageio
import PIL.Image as Image
import matplotlib.pyplot as plt
import data_storage as ds

with open('logging.yaml', 'r') as f:
    log_cfg = yaml.safe_load(f.read())
logging.config.dictConfig(log_cfg)

class ClientSocket:
    """
    Contains the socket objects for basic operations:
    - open a socket
    - close a socket
    """
    @classmethod
    def __init_subclass__(cls, connect = True, address = None, port = None, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self):
        self.logger = logging.getLogger("ClientSocket")
        self.logger.setLevel(logging.INFO)
        self.sock = None
        self.bufflen = 4096 #Buffer length for large data transfers             
        self.sara_addresses()

    def open_socket(self, address, port):
        """
        Open a TCP/IP socket
        """
        self.address = address
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = (address, port)
        self.sock.settimeout(30)
        self.sock.setblocking(True)
        try:
            self.logger.info('Opening socket. Addr: %s, Port: %d', self.server_address[0], self.server_address[1])
            self.sock.connect(self.server_address)
            self.logger.info('Opened socket. Addr: %s, Port: %d', self.server_address[0], self.server_address[1])
            self.sock.settimeout(30)
            self.sock.setblocking(True)
            return 0
        except:
            self.logger.error('Openening socket timed out: %s, Port: %d', self.server_address[0], self.server_address[1])
            return 1
        
    def close_socket(self):
        """
        Close a TCP/IP socket
        """
        self.sock.close()
        self.logger.info('Closed socket. Addr: %s, Port: %d', self.server_address[0], self.server_address[1])

    def sara_addresses(self):
        """
        Returns a dictionary of default ports and addresses
        """
        self.ports = {}
        self.ports["camera"]     = 1916 #985
        self.ports["focus"]      = 1911 #980
        self.ports["lasgo"]      = 1901 #996
        self.ports["lasgo_txt"]  = 1902 #994
        self.ports["spec"]       = 1920 #983
        
        self.addresses = {}
        self.addresses["CHESS"] = "128.84.183.184"
        self.addresses["LSA"] = "128.253.129.74"
        self.addresses["Analysis"] = "128.253.129.71"
        self.addresses["Local"] = socket.gethostname()
        return 

    def autoconnect(self, connect, address, port):
        """
        Select appropriate address and connect, if possible
        """
        if address in self.addresses:
            address_connect = self.addresses[address]
        else:
            address_connect = address
        if port in self.ports:
            if address == "Local":
                self.ports[port] += 1000
            port_connect = self.ports[port]
        else:
            port_connect = port
        if connect:
            success = self.open_socket(address_connect, port_connect)
        self.address = address_connect
        self.port = port_connect
        return success

class ClientLasGoProtocol(ClientSocket):
    """
    LasGo subclass.
    Text-based protocol for LasGo. 
    Relies on ClientSocket class and implements the 
    protocols to operate the LasGo stage and,
    eventually, the laser.
    """
    def __init__(self, connect = True, address = None, port = None):
        super(ClientLasGoProtocol, self).__init__()
        self.logger = logging.getLogger("ClientLasGo")
        self.txt_bufflen = 256 #Maximal string length
        self.io = 100
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "lasgo_txt"
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1
            
    def comm_structure_format(self, length = None):
        """
        Structure format of a string of given length (default is
        self.txt_bufflen).
        Returns the structure format and the structure itself.
        """
        if length is None:
            length = self.txt_bufflen - 1
        s_struct = ">" + str(length + 1) + "s"
        return s_struct, struct.Struct(s_struct)

    def comm_pack_data(self, packer, msg):
        """
        Structure packer for communication.
        Returns the packed structured string, and the utf-8 encoded string values
        """
        #values = msg.ljust(self.txt_bufflen).encode('utf-8')
        values = msg.encode('utf-8')
        packed_data = packer.pack(values)
        return packed_data, values

    def comm_unpack_data(self, unpacker, packed_data):
        """
        Converts the packed data to a readable string, 
        and truncates everyting after \x00, the termination character from C.
        Returns the unpacked string.
        """
        unpacked_data = unpacker.unpack(packed_data)
        msg = unpacked_data
        msg = list(msg)[0]
        #Here we truncate the message at the "end" #indentified by '\x00'
        msg = msg.decode('utf-8', errors = "ignore")
        if '\x00' in msg:
            msg = msg.split('\x00', 1)[0]
        return msg

    def comm_send_struct(self, msg_out):
        """
        Sends the message string to the socket.
        """
        if len(msg_out) > self.txt_bufflen:
            self.logger.error("Message length for LasGo comm must be less than %d, but receveived %d",
                                 self.txt_bufflen, len(msg_out))
            self.close_socket()
            #Upon error set self.io != 0
            self.io = 1
            return
        try:
            s_struct, packer = self.comm_structure_format(len(msg_out))
            packed_data, values = self.comm_pack_data(packer, msg_out)
            self.logger.debug('Sending %s, %s', binascii.hexlify(packed_data), msg_out)
            self.sock.sendall(packed_data) #Send data
            self.logger.info("Sent %s", msg_out)
            self.io = 0
        except:
            self.io = 1
            self.logger.error("Send not successful comm_send_struct")
        return 

    def comm_recv_struct_len(self):
        """
        Receives data and splits it up into appropriate chunks:
        The data format is as follow:
        first the length of the string, then the data, in the following format: 
            000014:15.317 -28.002 
        The first part (6 digits) indicates the total length of the message,
        followed by a colon.
        Then, the main message follows, which is returned here
        """
        s_struct = ">7s" #First 6 digits, then a semicolon
        unpacker = struct.Struct(s_struct)
        try:
            packed_data = self.sock.recv(unpacker.size)
            #print(packed_data)
            msg_in = self.comm_unpack_data(unpacker, packed_data)
            self.logger.debug('Received header %s, %s',  binascii.hexlify(packed_data), msg_in)
            length = int(msg_in[:6])
            length_msg = length
            #print("Message length to be received",length_msg)
            s_struct = ">" + str(length_msg) + "s" #The complete message to be received
            unpacker = struct.Struct(s_struct)
            packed_data = self.sock.recv(unpacker.size)
            #empty_cache = self.sock.recv(4096)
            #print('received "%s"' % binascii.hexlify(packed_data))
            msg_in = self.comm_unpack_data(unpacker, packed_data)
            self.logger.debug('Received data %s, %s', binascii.hexlify(packed_data), msg_in)
            #print("Message reveived:", msg_in)
            self.logger.info("Received %s", msg_in)
            self.io = 0
        except:
            self.io = 1
            self.logger.error("Receive not successful comm_recv_struct_len")
            msg_in = None
        return msg_in


    def send_recv(self, msg):
        """
        Sends message, and upon success, attempts to receive respons
        """
        self.comm_send_struct(msg)
        if not self.io == 0 : return
        msg_recv = self.comm_recv_struct_len()
        return msg_recv

        """
        The following section contains the actual set of 
        functions to control LASGO
        ****************************************************************************
        """
    def get_version(self):
        """
        Returns the version of the stage software.
        """
        msg = "QV"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return int(-1)
        return int(msg_recv)

    def moveto(self, x, y):
        """
        Moves the stage to position x and y in mm, in user coordinates.
        """
        msg = "MV " + str(float(x)) + " " + str(float(y))
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed moveto %s", msg_recv)
            self.io = 2
        return 

    def moveto_queue(self, x, y):
        """
        Moves the stage to position x and y in mm queued, in user coordinates.
        """
        msg = "BM " + str(float(x)) + " " + str(float(y))
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed moveto %s", msg_recv)
            self.io = 2
        return 

    def get_position(self):
        """
        Returns the current position of the stage in user coordinates.
        """
        msg = "GP"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return [-1.e10, -1.e10] 
        return [float(x) for x in msg_recv.split()]

    def get_device(self):
        """
        Returns the device index and name (not yet implemented).
        """
        msg = "QO"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return -10000, "None"
        msg_recv = msg_recv.split()
        devname = ""
        for n in msg_recv[1:]:
            devname += n + " "
        return int(msg_recv[0]), devname

    def set_device(self, org):
        """
        Sets the device index or name if org is a string instead of type int
        """
        if isinstance(org, int):    
            msg = "SO " + str(org)
        elif isinstance(org, str):
            msg = "SO " + org
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed set_device %s", msg_recv)
            self.io = 2
        return 

    def wait(self):
        """
        Blocks communication until the queued command has been correctly
        executed.
        """
        msg = "WA"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed wait %s", msg_recv)
            self.io = 2
        return 

    def abort(self):
        """
        Aborts requested action
        """
        msg = "AB"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed abort %s", msg_recv)
            self.io = 2
        return 

    def panic(self):
        """
        Shuts down everything
        """
        msg = "PA"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return
        if msg_recv != "0":
            self.logger.warning("Failed panic %s", msg_recv)
            self.io = 2
        return 

    def status(self):
        """
        Returns status information as a dictionary
        """
        msg = "ST"
        msg_recv = self.send_recv(msg)
        if not self.io == 0 : return None 
        msg_float = [float(x) for x in msg_recv.split()]
        dict_data = {}
        dict_data["rc"] =          int(msg_float[0])
        dict_data["full_status"] = int(msg_float[1])
        dict_data["x_status"] =    int(msg_float[2])
        dict_data["y_status"] =    int(msg_float[3])
        dict_data["x_pos_rel"] =   float(msg_float[4])
        dict_data["y_pos_rel"] =   float(msg_float[5])
        dict_data["x_pos_abs"] =   float(msg_float[6])
        dict_data["y_pos_abs"] =   float(msg_float[7])
        dict_data["x_pos_fb"] =    float(msg_float[8])
        dict_data["y_pos_fb"] =    float(msg_float[9])
        dict_data["x_pos_err"] =   float(msg_float[10])
        dict_data["y_pos_err"] =   float(msg_float[11])
        dict_data["x_vel"] =       float(msg_float[12])
        dict_data["y_vel"] =       float(msg_float[13])
        return dict_data

    def moveto_safe(self, pos):
        """
        Wrapper to move position, and check it the move was successful
        Will return 0 if successful, 1 otherwise
        """
        tol = 0.0015
        self.moveto_queue(pos[0], pos[1])
        poscur = self.get_position()
        diff = np.linalg.norm(np.array(pos)-np.array(poscur))
        if diff > tol:
            self.logger.warning("The stage movement not at required precision %f", diff)
            return 1
        else:
            return 0

class ClientStructProtocol(ClientSocket):
    """
    General structure-based protocol class. 
    Relies on ClientSocket class.
    This class is used to communicate with cameras, spectrometers, XRD, etc.
    and is suited to exchange large amount of data.
    """
    @classmethod
    def __init_subclass__(cls, connect = True, address = None, port = None, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self):
        super(ClientStructProtocol, self).__init__()
        self.logger = logging.getLogger("ClientStruct")
        self.crc = True

    def comm_structure_format(self):
        """
        Returns the communication structure format, 
        containing 5 integers of length 32, big endian (if CRC is included),
        and 4 integers without CRC
        The default communication method to send requests.
        0: msg, the message index
        1: msgid, tag to track messages
        2: option, single parameter for enhancing some msg
        3: rc, return code, zero on success, other values depending on request task
        4: data_size, length of data send in following send requests
        5: crc32 (optional), CRC32 checksum of the data to be transmitted in subsequent comm.
        """
        if self.crc:
            s_struct = ">I i i i I I"
        else:
            s_struct = ">I i i i I"
        return s_struct, struct.Struct(s_struct)

    def get_crc(self, data):
        """
        Returns crc32 of the data package
        """
        crc32 = zlib.crc32(data)  & 0xFFFFFFFF 
        return crc32
 
    def pack_data(self, packer, msg):
        """
        Returns the general packed message based on packer.
        """
        if isinstance(msg, list):
            values = tuple(msg)
            packed_data = packer.pack(*values)
        else:
            values = msg
            packed_data = packer.pack(values)
        return packed_data, values

    def unpack_data(self, unpacker, packed_data):
        """
        Returns the general unpacked message based on unpacker
        """
        unpacked_data = unpacker.unpack(packed_data)
        msg = list(unpacked_data[:])
        return msg

    def comm_pack_data(self, packer, msg):
        """
        Returns the packed message based on packer specifically for the
        communication protocol.
        """
        if len(msg) < 5 or len(msg) > 6:
            self.logger.error("Length of comm message not between 5 and 6, but %d", len(msg))
        values = tuple(msg)
        packed_data = packer.pack(*values)
        return packed_data, values

    def comm_unpack_data(self, unpacker, packed_data):
        """
        Returns the unpacked message based on unpacker specifically for the
        communication protocol.
        """
        unpacked_data = unpacker.unpack(packed_data)
        msg = list(unpacked_data[:])
        return msg

    def string_packer_format(self, length):
        """
        Structure format of a string of given length 
        Returns the structure format and the structure itself.
        """
        s_struct = ">" + str(length) + "s"
        return s_struct, struct.Struct(s_struct)

    def comm_send_struct(self, msg_out):
        """
        Sends communication data.
        Wrapper to send data based specifically for the communication protocol.
        """
        if self.crc:
            if len(msg_out) != 6:
                self.logger.error("Message length for Struct comm must be exactly 6, but %d", len(msg_out))
                return
        else:
            if len(msg_out) != 5:
                self.logger.error("Message length for Struct comm must be exactly 5, but %d", len(msg_out))
                return

        s_struct, packer = self.comm_structure_format()
        packed_data, values = self.comm_pack_data(packer, msg_out)
        
        # Send data
        self.logger.info("Sending "+':'.join([str(i) for i in msg_out]))
        self.logger.debug("Sending %s", binascii.hexlify(packed_data))
        self.sock.sendall(packed_data)

    def comm_recv_struct(self, msg_out):
        """
        Receivs communication data and compares with the initial 
        outgoing message (msg_out) for any errors.
        Wrapper to receive data based specifically for the communication
        protocol.
        Returns the received message.
        """
        if self.crc:
            if len(msg_out) != 6:
                self.logger.error("Message length for Struct comm must be exactly 6, but %d", len(msg_out))
                return
        else:
            if len(msg_out) != 5:
                self.logger.error("Message length for Struct comm must be exactly 5, but %d", len(msg_out))
                return

        s_struct, unpacker = self.comm_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        msg_in = self.comm_unpack_data(unpacker, packed_data)
        self.logger.info("Received "+':'.join([str(i) for i in msg_in]))
        self.logger.debug("Received %s", binascii.hexlify(packed_data))

        #Check message for consistency
        if msg_in[0] != msg_out[0] or msg_in[1] != msg_out[1]:
            self.logger.error("Reply inconsistency on Struct comm: %d:%d, %d:%d", msg_in[0], msg_out[0], msg_in[1], msg_out[1])
            return
        if msg_in[0] != 1 and msg_in[3] != msg_out[3]:
            self.logger.warning("RC value returned non-zero %d, %d:%d", msg_in[0], msg_in[3], msg_out[3])
        return msg_in

    def recv_data_buffered(self, unpacker, msg_recv, fixed_size = None):
        """
        For receiving large amount of data, use this
        buffered transfer protocol
        """ 
        if fixed_size is None:
            if msg_recv[4] != unpacker.size:
                self.logger.error("Unpacker size does not match the expected data size %d:%d", msg_recv[4], unpacker.size)
                return
        else:
            if fixed_size != unpacker.size:
                self.logger.error("Unpacker size does not match the expected, fixed data size %d:%d", fixed_size, unpacker.size)
                return
        
        self.logger.info("Receiving first block")

        packed_data = bytearray(unpacker.size)
        pos = 0
        while pos < unpacker.size:
            cr = self.sock.recv_into(memoryview(packed_data)[pos:])
            if cr == 0:
                raise EOFError
            pos += cr
        amount_received = pos
        ##packed_data = self.sock.recv(min(self.bufflen, unpacker.size))
        ##print(type(packed_data))
        ##self.logger.debug("Received %s", binascii.hexlify(packed_data))
        ##amount_received = len(packed_data)
        ##while amount_received < unpacker.size:
        ##    self.logger.info("Block no x")
        ##    packed_data += self.sock.recv(min(self.bufflen, unpacker.size - amount_received))
        ##    amount_received = len(packed_data)
        ###print("Amount of data expected/received", unpacker.size, amount_received)
        self.logger.info("Received last block")
        if unpacker.size != amount_received:
            self.logger.error("Data loss during transfer of wavelength data %d:%d", unpacker.size, amount_received)
            return
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        return data_recv

    def recv_data_buffered_raw(self, fixed_size):
        """
        For receiving large amount of data as a datastream
        """ 
        self.logger.info("Receiving first block")

        packed_data = bytearray(fixed_size)
        pos = 0
        while pos < fixed_size:
            cr = self.sock.recv_into(memoryview(packed_data)[pos:])
            if cr == 0:
                raise EOFError
            pos += cr
        amount_received = pos
        self.logger.info("Received last block")
        if fixed_size != amount_received:
            self.logger.error("Data loss during transfer of wavelength data %d:%d", fixed_size, amount_received)
            return
        return packed_data

    def check_msgid(self, msg_id, msg_recv):
        consistent = True
        if msg_id != msg_recv[1]:
            self.logger.error("Message ID inconsistency, %d %d", msg_id, msg_recv[1])
            consistent = False
        return consistent

    def check_crc(self, packed_data, msg_recv):
        consistent = True
        if self.crc:
            crc = self.get_crc(packed_data)
            if crc != msg_recv[5]:
                self.logger.warning("CRC mismatch %d:%d", crc, msg_recv[5])
                consistent = False
        return consistent

class ClientLasGoProtocol_Struct(ClientStructProtocol):
    """
    LasGo subclass.
    Structure-based protocol for LasGo. 
    Relies on the ClientStructProtocol class and implements the 
    protocols to operate the LasGo stage the laser.
    NOTE: only this protocol can deal with the laser part of the LasGo protocol
    """
    def __init__(self,  connect = True, address = None, port = None):
        super(ClientLasGoProtocol_Struct, self).__init__()
        self.logger = logging.getLogger("ClientLasGo")
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "lasgo" 
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1

    def POSN_structure_format(self):
        """
        Returns structure format of the POSN.
        Used to send and/or receive x y format doubles
        """
        s_struct  = "<"
        s_struct += "d "   #x
        s_struct += "d "   #y
        return s_struct, struct.Struct(s_struct)

    def set_SERVER_END(self, msg_id):
        """
        Shuts down the LasGo server.
        """
        msg = [0, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return msg_recv[3]

    def get_LASGO_QUERY_VERSION(self, msg_id):
        """
        Returns version of the LasGo server.
        """
        msg = [1, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Server version %d", msg_recv[3])
        return msg_recv[3]

    #Block dealing with LASGO_GET_TRANSFORM*****************************************
    def LASGO_GET_TRANSFORM_structure_format(self):
        """
        Returns structure format of the coordinate transformation.
        """
        s_struct  = "<"
        s_struct_pos, packer_pos   = self.POSN_structure_format() 
        s_struct += s_struct_pos[1:]  #Origin of user space in world coordinates
        s_struct += s_struct_pos[1:]  #Multiplicative scaling
        s_struct += "d"               #Rotation angle
        return s_struct, struct.Struct(s_struct)

    def LASGO_GET_TRANSFORM_todict(self, data_list):
        """
        Transform list to dictionary of LASGO_GET_TRANSFORM structure
        """
        data_dict = {}
        data_dict['origin']     = [data_list[0], data_list[1]]
        data_dict['scaling']    = [data_list[2], data_list[3]]
        data_dict['angle']      = data_list[4] 
        return data_dict

    def get_LASGO_GET_TRANSFORM(self, msg_id):
        """
        Wrapper function to get the coordinate transformation info.
        """
        msg = [2, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_GET_TRANSFORM_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.LASGO_GET_TRANSFORM_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with LASGO_GET_TRANSFORM*****************************************

    #Block dealing with LASGO_QUERY_ORIGIN*****************************************
    def LASGO_QUERY_ORIGIN_structure_format(self):
        """
        Returns structure format of the lasgo origin.
        """
        s_struct  = "<"
        s_struct += "32s "                                      #Label for the origin on the main screen 
        s_struct_pos, packer_pos = self.POSN_structure_format() #World (X,Y) coordinates of the origin 
        s_struct += s_struct_pos[1:]
        return s_struct, struct.Struct(s_struct)

    def LASGO_QUERY_ORIGIN_todict(self, data_list):
        """
        Transform list to dictionary of LASGO_QUERY_ORIGIN structure
        """
        data_dict = {}
        data_dict['label']  = data_list[0].decode('utf-8', errors = "ignore").split('\x00', 1)[0] 
        data_dict['origin'] = [data_list[1], data_list[2]]
        return data_dict

    def get_LASGO_QUERY_ORIGIN(self, msg_id):
        """
        Wrapper function to get lasgo origin.
        """
        msg = [3, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_QUERY_ORIGIN_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.LASGO_QUERY_ORIGIN_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with LASGO_QUERY_ORIGIN*****************************************

    def set_LASGO_SET_ORIGIN(self, msg_id, org):
        """
        Sets the device index, or its name if org is a string instead of type int
        """
        msg = [4, msg_id, 0, 0, 0]
        if isinstance(org, int):    
            msg[2] = org
            if self.crc:
               msg.append(0) 
            self.comm_send_struct(msg)
        elif isinstance(org, str):
            msg[2] = -1 
            org_c = org.encode('utf-8')
            data = [org_c]
            s_struct, packer = self.string_packer_format(len(data[0]))
            packed_data, values = self.pack_data(packer, data)
            msg[4] = packer.size
            if self.crc:
                crc = self.get_crc(packed_data)
                msg.append(crc)
            self.comm_send_struct(msg)
            # Send data
            self.sock.sendall(packed_data)
        else:
            self.logger.error("Origin has to be a string or an integer")
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Passed origin ID could not be located")
        elif int(msg_recv[3]) == -2:
            self.logger.error("General origin error")
        elif int(msg_recv[3]) < -2:
            self.logger.error("Origin could not be set")
        return msg_recv[3]

    def get_LASGO_GET_POSN(self, msg_id, cordsys):
        """
        Wrapper function to get the current coordinate.
        If cordsys is 0, the coordinate in the world space (absolute) is
        returned
        For cordsys != 0, the user coordinates are returned
        """
        msg = [5, msg_id, int(cordsys), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.POSN_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        if int(msg_recv[3]) != 0:
            self.logger.error("Could not get current position")
        return data_recv

    def set_LASGO_MOVE_TO(self, msg_id, cordsys, pos):
        """
        Wrapper function to set the current coordinate.
        If cordsys is 0, the coordinate in the world space (absolute)
        For cordsys != 0, the user coordinates
        pos must be a list with 2 elements, x and y
        """
        msg = [6, msg_id, int(cordsys), 0, 0]
        s_struct, packer = self.POSN_structure_format()
        if len(pos) != 2:
            self.logger.error("Variable pos in set_LASGO_MOVE_TO must be of length 2, %d", len(pos))
            return
        packed_data, values = self.pack_data(packer, [float(pos[0]), float(pos[1])])
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Could not set current position")
        return msg_recv[3]

    def set_LASGO_QUEUE_TO(self, msg_id, cordsys, pos):
        """
        Wrapper function to set the current coordinate.
        If cordsys is 0, the coordinate in the world space (absolute)
        For cordsys != 0, the user coordinates
        pos must be a list with 2 elements, x and y
        Returns immediately after receiving the command without waiting to
        complete
        """
        msg = [7, msg_id, int(cordsys), 0, 0]
        s_struct, packer = self.POSN_structure_format()
        packed_data, values = self.pack_data(packer, [float(pos[0]), float(pos[1])])
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Could not set current position")
        return msg_recv[3]

    def get_LASGO_WAIT_MOVE_DONE(self, msg_id):
        """
        Waits until any complex operation is completed.
        """
        msg = [8, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return msg_recv[3]

    #Block dealing with LASGO_QUERY_RAW_STATUS*****************************************
    def LASGO_QUERY_RAW_STATUS_structure_format(self):
        """
        Returns structure format of the lasgo status.
        """
        s_struct  = "<"
        s_struct += "i "   #Axes and scan thread status flag
        s_struct += "i "   #U500 status falgs
        s_struct += "i "   #int X_axis_status
        s_struct += "i "   #int Y_axis_status
        s_struct += "d d " #x_relative, y_relative
        s_struct += "d d " #x_absolute, y_absolute
        s_struct += "d d " #x_feedback, y_feedback
        s_struct += "d d " #x_poserror, y_poserror
        s_struct += "d d " #x_velocity, y_velocity
        return s_struct, struct.Struct(s_struct)

    def LASGO_QUERY_RAW_STATUS_todict(self, data_list):
        """
        Transform list to dictionary of LASGO_QUERY_RAW_STATUS structure
        """
        data_dict = {}
        data_dict['status']        = data_list[0]
        data_dict['U500_status;']  = data_list[1]
        data_dict['x_status']      = data_list[2]  #int X_axis_status
        data_dict['y_status']      = data_list[3]  #int Y_axis_status
        data_dict['x_pos_rel']     = data_list[4]  #x_relative, y_relative
        data_dict['y_pos_rel']     = data_list[5]  #x_relative, y_relative
        data_dict['x_pos_abs']     = data_list[6]  #x_absolute, y_absolute
        data_dict['y_pos_abs']     = data_list[7]  #x_absolute, y_absolute
        data_dict['x_pos_fb']      = data_list[8]  #x_feedback, y_feedback
        data_dict['y_pos_fb']      = data_list[9]  #x_feedback, y_feedback
        data_dict['x_pos_err']     = data_list[10] #x_poserror, y_poserror
        data_dict['y_pos_err']     = data_list[11] #x_poserror, y_poserror
        data_dict['x_vel']         = data_list[12] #x_velocity, y_velocity
        data_dict['y_vel']         = data_list[13] #x_velocity, y_velocity
        return data_dict

    def get_LASGO_QUERY_RAW_STATUS(self, msg_id):
        """
        Wrapper function to get lasgo status.
        """
        msg = [9, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_QUERY_RAW_STATUS_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.LASGO_QUERY_RAW_STATUS_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with LASGO_QUERY_RAW_STATUS*****************************************

    def set_LASGO_ABORT_MOVE(self, msg_id, timeout):
        """
        Aborts a move after waiting for timeout (in ms)
        """
        msg = [10, msg_id, int(timeout), 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return msg_recv[3]

    def set_LASGO_PANIC(self, msg_id, timeout):
        """
        Aborts any action after waiting for timeout (in ms)
        """
        msg = [10, msg_id, int(timeout), 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return msg_recv[3]

    #Block dealing with LASGO_EXECUTE_FLYSCAN*****************************************
    def LASGO_EXECUTE_FLYSCAN_structure_format(self):
        """
        Returns structure format of the lasgo flyscan.
        """
        s_struct_pos, packer_pos = self.POSN_structure_format() #World (X,Y) coordinates of the origin 
        s_struct  = "<"
        s_struct += "I "                #User or World coordinates, should be boolean
        s_struct += s_struct_pos[1:]    #Start position in mm
        s_struct += s_struct_pos[1:]    #End position in mm
        s_struct += "d "                #Scan velocity
        s_struct += "d "                #msRampTime
        s_struct += "d "                #gMaxAccel
        s_struct += "d "                #mmConstVel
        s_struct += "d "                #mmTriggerSpacing
        return s_struct, struct.Struct(s_struct)

    def LASGO_EXECUTE_FLYSCAN_CHESS2021_structure_format(self):
        """
        Returns structure format of the lasgo flyscan.
        """
        s_struct_pos, packer_pos = self.POSN_structure_format() #World (X,Y) coordinates of the origin 
        s_struct  = "<"
        s_struct += "I "                #User or World coordinates, should be boolean
        s_struct += s_struct_pos[1:]    #Start position in mm
        s_struct += s_struct_pos[1:]    #End position in mm
        s_struct += "d "                #Integration time in ms
        s_struct += "I "                #Number of frames between start and stop
        return s_struct, struct.Struct(s_struct)

    def LASGO_EXECUTE_FLYSCAN_tolist(self, data_dict):
        """
        From a dict, return the data in the correct order to perform a flyscan
        """
        data_list = []
        data_list.append(data_dict["cordsys"])
        data_list.append(data_dict["pos_start"][0])
        data_list.append(data_dict["pos_start"][1])
        data_list.append(data_dict["pos_end"][0])
        data_list.append(data_dict["pos_end"][1])
        data_list.append(data_dict["vel"])
        data_list.append(data_dict["msRampTime"])                      
        data_list.append(data_dict["gMaxAccel"])        
        data_list.append(data_dict["mmConstVel"])       
        data_list.append(data_dict["mmTriggerSpacing"]) 
        return data_list

    def LASGO_EXECUTE_FLYSCAN_CHESS2021_tolist(self, data_dict):
        """
        From a dict, return the data in the correct order to perform a flyscan
        """
        data_list = []
        data_list.append(data_dict["cordsys"])
        data_list.append(data_dict["pos_start"][0])
        data_list.append(data_dict["pos_start"][1])
        data_list.append(data_dict["pos_end"][0])
        data_list.append(data_dict["pos_end"][1])
        data_list.append(data_dict["int_time"])
        data_list.append(data_dict["nframes"])                      
        return data_list

    def dict_LASGO_EXECUTE_FLYSCAN(self):
        """
        The format of the flyscan dictionary
        """
        data_dict = {}
        data_dict["cordsys"]            = None #int:   0 and 1 for user or world coordinates
        data_dict["pos_start"]          = None #float: list of 2, x and y
        data_dict["pos_end"]            = None #float: list of 2, x and y
        data_dict["vel"]                = None #float: scan velocity
        data_dict["msRampTime"]         = None #float: ms for ramping to vel 
        data_dict["gMaxAccel"]          = None #float: maximum g's of accelerateion 
        data_dict["mmConstVel"]         = None #float: mm of constant velocity before shutter 
        data_dict["mmTriggerSpacing"]   = None #float: spacing between collection triggers 
        return data_dict

    def dict_LASGO_EXECUTE_FLYSCAN_CHESS2021(self):
        """
        The format of the flyscan dictionary
        """
        data_dict = {}
        data_dict["cordsys"]            = None #int:   0 and 1 for user or world coordinates
        data_dict["pos_start"]          = None #float: list of 2, x and y
        data_dict["pos_end"]            = None #float: list of 2, x and y
        data_dict["int_time"]           = None #float: integration time
        data_dict["nframes"]         = None #int: number of frames
        return data_dict

    def set_LASGO_EXECUTE_FLYSCAN(self, msg_id, data_dict):
        """
        Wrapper function to perform a fly scan
        Command is not blocking!!
        get_LASGO_QUERY_STATUS must be called to check if the scan is complete
        """
        msg = [12, msg_id, 0, 0, 0]
        data_list = self.LASGO_EXECUTE_FLYSCAN_tolist(data_dict)
        s_struct, packer = self.LASGO_EXECUTE_FLYSCAN_structure_format()
        packed_data, values = self.pack_data(packer, data_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            if int(msg_recv[3]) == -1:
                self.logger.error("Thread for running a stripe is currently active")
            if int(msg_recv[3]) == 1:
                self.logger.error("Velocity request out of range")
            if int(msg_recv[3]) == 2:
                self.logger.error("Acceleration exceeds max G")
            if int(msg_recv[3]) == 3:
                self.logger.error("Stage position with accel/decel exceeds stage dimensions")
            if int(msg_recv[3]) == 4:
                self.logger.error("Failed to start the thread to actually scan")
        return msg_recv[3]

    def set_LASGO_EXECUTE_FLYSCAN_CHESS2021(self, msg_id, data_dict):
        """
        Wrapper function to perform a fly scan
        Command is not blocking!!
        get_LASGO_QUERY_STATUS must be called to check if the scan is complete
        """
        msg = [12, msg_id, 0, 0, 0]
        data_list = self.LASGO_EXECUTE_FLYSCAN_CHESS2021_tolist(data_dict)
        s_struct, packer = self.LASGO_EXECUTE_FLYSCAN_CHESS2021_structure_format()
        packed_data, values = self.pack_data(packer, data_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            if int(msg_recv[3]) == -1:
                self.logger.error("Thread for running a stripe is currently active")
            if int(msg_recv[3]) == 1:
                self.logger.error("Velocity request out of range")
            if int(msg_recv[3]) == 2:
                self.logger.error("Acceleration exceeds max G")
            if int(msg_recv[3]) == 3:
                self.logger.error("Stage position with accel/decel exceeds stage dimensions")
            if int(msg_recv[3]) == 4:
                self.logger.error("Failed to start the thread to actually scan")
        return msg_recv[3]
    #Block dealing with LASGO_EXECUTE_FLYSCAN*****************************************

    #Block dealing with LASGO_QUERY_FLYSCAN_TRIG*****************************************
    def LASGO_QUERY_FLYSCAN_TRIG_structure_format(self, samples):
        """
        Returns structure format of the lasgo flyscan.
        """
        s_struct  = "<"
        for i in range(samples):
            s_struct += "d d " #x,y;			    Position of stage at time of trigger
            s_struct += "d "   #time;	            Time of trigger relative to first one
            s_struct += "d d " #pretime, posttime;	Delta time for call to aerq and posttime after trigger
            s_struct += "d "   #beam_current;		Beam current at time of trigger
        return s_struct, struct.Struct(s_struct)

    def LASGO_QUERY_FLYSCAN_TRIG_todict(self, samples, data_list):
        """
        Returns structure format of the lasgo flyscan.
        """
        data_dict_list = []
        count = 0
        for i in range(samples):
            data_dict = {}
            data_dict["pos"] = [data_list[count], data_list[count + 1]]
            count += 2
            data_dict["time"] = data_list[count]
            count += 1
            data_dict["pretime"] = data_list[count]
            count += 1
            data_dict["posttime"] = data_list[count]
            count += 1
            data_dict["beam_current"] = data_list[count]
            count += 1
            data_dict_list.append(data_dict)
        return data_dict_list

    def get_LASGO_QUERY_FLYSCAN_TRIG(self, msg_id):
        """
        Wrapper function to get flyscan triggers
        """
        msg = [13, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        samples = msg_recv[3]
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_QUERY_FLYSCAN_TRIG_structure_format(samples)
        msg_recv_mod = cp.deepcopy(msg_recv)
        msg_recv_mod[4] = unpacker.size #This should be samples * unpacker size of a single trigger
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_dict_list = self.LASGO_QUERY_FLYSCAN_TRIG_todict(samples, data_recv)
        return data_dict_list 
    #Block dealing with LASGO_QUERY_FLYSCAN_TRIG*****************************************

    #Block dealing with LASGO_GET_JOB_STRUCT*****************************************
    def LASER_DELAYS_structure_format(self):
        """
        Returns structure format of the lasgo delays
        """
        s_struct  = "<"
        s_struct += "d "    # Warmup_Delay,  Power warmup time in seconds      
        s_struct += "d "    # Warmup_Power,  Power warmup power in watts      
        s_struct += "d "    # Change_Delay,  Seconds (constant) on power change
        return s_struct, struct.Struct(s_struct)

    def LASER_DELAYS_todict(self, data_list):
        """
        Returns a dictionary of the delay structure
        """
        data_dict = {} 
        data_dict["WarmupDelay"] = data_list[0] # Power warmup time in seconds
        data_dict["WarmupWatts"] = data_list[1] # Power warmup power in watts
        data_dict["ChangeDelay"] = data_list[2] # Seconds (constant) on power change
        return data_dict

    def LASER_DELAYS_tolist(self, data_dict):
        """
        Returns a list of the delay dictionary
        """
        data_list = []
        data_list.append(data_dict["WarmupDelay"]) # Power warmup time in seconds
        data_list.append(data_dict["WarmupWatts"]) # Power warmup power in watts
        data_list.append(data_dict["ChangeDelay"]) # Seconds (constant) on power change
        return data_list

    def LASGO_JOB_STRUCT_structure_format(self):
        """
        Returns structure format of the lasgo job for LSA
        """
        s_struct_delay, struct_delay = self.LASER_DELAYS_structure_format()
        s_struct  = "<"
        s_struct += "I "    #magic;				                Magic ID to validate entry		
        s_struct += "I "    #version;	                        Version of this structure			
        s_struct += "I "    #StageParmErrors;	                Stage parameters (vel/ramp time) ok for request vel?
        s_struct += "80s "  #id[80];			                Identification string				
        s_struct += "256s " #path[256];
        s_struct += "I "    #ZONE head
        s_struct += "d "    #RampTime;			                Velocity ramp time (ms)	
        s_struct += "d "    #MaxAccel;			                Maximum acceleration on stage (g)	
        s_struct += "d "    #CVDist;				            Constant velocity distance (mm)	
        s_struct += "I "    #Velocity_Priority;		            Velocity has priority over dwell		
        s_struct += "I "    #Exclude;				            If TRUE, limit laser to wafer		
        s_struct += "I "    #ManualPowerSet;		            If TRUE, manually set powers 		
        s_struct += "d "    #WaferDiameter;			            Wafer diameter (if excluded) (mm)
        s_struct += "d "    #EdgeExclusion;			            Edge exclusion (if excluded) (mm)
        s_struct += s_struct_delay[1:] #LASER_DELAYS CO2;	Power handling for CO2 			
        s_struct += s_struct_delay[1:] #LASER_DELAYS LD;	Power handling for laser diode 	
        s_struct += "i i "  #CO2_Origin, LD_Origin;	            Index to origin for CO2 and LD lasers (<0 => default) 
        s_struct += "I "    #Load_Wafer;			            Move to load position and wait
        s_struct += "I "    #Unload_Wafer;			            Move to load position and wait
        s_struct += "I "    #UseRobustPower;		            Is power to be measured/verified
        s_struct += "d "    #PowerSettleTime;                   Power settling time on robust
        s_struct += "d d "  #MinRetraceVel, MaxRetraceVel;      Retrace limits when not on power scan
        s_struct += "I "    #OffsetEnable;			            Enable offset value for shift of pattern
        s_struct += "d d "  #Offset_X, Offset_Y;	            X and Y offset
        return s_struct, struct.Struct(s_struct)

    def LASGO_JOB_STRUCT_todict(self, data_list):
        """
        Returns a dictionary of the job structure
        """
        data_dict = {} 
        data_dict["magic"]              = data_list[0]   # Magic ID to validate entry
        data_dict["version"]            = data_list[1]   # Version of this structure		
        data_dict["StageParmErrors"]    = data_list[2]   # Stage parameters (vel/ramp time) ok for request vel?
        data_dict["ID"]                 = data_list[3].decode('utf-8', errors = "ignore").split('\x00', 1)[0]	# Identification string
        data_dict["path"]               = data_list[4].decode('utf-8', errors = "ignore").split('\x00', 1)[0]	# Path string
        data_dict["ZONE_head"]          = data_list[5]
        data_dict["RampTime"]           = data_list[6]   # Velocity ramp time (ms)	
        data_dict["MaxAccel"]           = data_list[7]   # Maximum acceleration on stage (g)	
        data_dict["CVDist"]             = data_list[8]   # Constant velocity distance (mm)	
        data_dict["VelocityPriority"]   = data_list[9]   # Velocity has priority over dwell		
        data_dict["Exclude"]            = data_list[10]  # If TRUE, limit laser to wafer		
        data_dict["ManualPowerSet"]     = data_list[11]  # If TRUE, manually set powers 		
        data_dict["WaferDiameter"]      = data_list[12]  # Wafer diameter (if excluded) (mm)
        data_dict["EdgeExclusion"]      = data_list[13]  # Edge exclusion (if excluded) (mm)
        data_dict["CO2"]                = self.LASER_DELAYS_todict(data_list[14:17]) #Power handling for CO2
        data_dict["LD"]                 = self.LASER_DELAYS_todict(data_list[17:20]) #Power handling for laser diode
        data_dict["CO2Origin"]	        = data_list[20]  # Index to origin for CO2 laser (<0 => default)
        data_dict["LDOrigin"]	        = data_list[21]  # Index to origin for LD laser (<0 => default) 
        data_dict["LoadWafer"]          = data_list[22]  # Move to load position and wait		
        data_dict["UnloadWafer"]        = data_list[23]  # Move to load position and wait	
        data_dict["UseRobustPower"]     = data_list[24]  # Is power to be measured/verified	
        data_dict["PowerSettleTime"]    = data_list[25]  # Power settling time on robust
        data_dict["MinRetraceVel"]      = data_list[26]  # Retrace limits when not on power scan
        data_dict["MaxRetraceVel"]      = data_list[27]  # Retrace limits when not on power scan	
        data_dict["OffsetEnable"]       = data_list[28]  # Enable offset value for shift of pattern
        data_dict["Offset_X"]           = data_list[29]  # X offset 	
        data_dict["Offset_Y"]           = data_list[30]  # Y offset
        return data_dict

    def LASGO_JOB_STRUCT_tolist(self, data_dict):
        """
        Returns a data list from a job structure
        """
        data_list = [] 
        data_list.append(data_dict["magic"])			      
        data_list.append(data_dict["version"])		      
        data_list.append(data_dict["StageParmErrors"])      
        data_list.append(data_dict["ID"].encode('utf-8'))  
        data_list.append(data_dict["path"].encode('utf-8')) 
        data_list.append(data_dict["ZONE_head"] )     
        data_list.append(data_dict["RampTime"])			  
        data_list.append(data_dict["MaxAccel"])			  
        data_list.append(data_dict["CVDist"])			      
        data_list.append(data_dict["VelocityPriority"])	  
        data_list.append(data_dict["Exclude"])			  
        data_list.append(data_dict["ManualPowerSet"])	      
        data_list.append(data_dict["WaferDiameter"])	      
        data_list.append(data_dict["EdgeExclusion"])		  
        data_list.extend(self.LASER_DELAYS_tolist(data_dict["CO2"]))           
        data_list.extend(self.LASER_DELAYS_tolist(data_dict["LD"]))           
        data_list.append(data_dict["CO2Origin"]) 
        data_list.append(data_dict["LDOrigin"])	          
        data_list.append(data_dict["LoadWafer"])			  
        data_list.append(data_dict["UnloadWafer"])		  
        data_list.append(data_dict["UseRobustPower"])		  
        data_list.append(data_dict["PowerSettleTime"])	  
        data_list.append(data_dict["MinRetraceVel"])        
        data_list.append(data_dict["MaxRetraceVel"])        
        data_list.append(data_dict["OffsetEnable"])         
        data_list.append(data_dict["Offset_X"])		      
        data_list.append(data_dict["Offset_Y"])		      
        return data_list

    def get_LASGO_GET_JOB_STRUCT(self, msg_id, option):
        """
        Returns the job structure:
            0   Returns the currently active job, sets to default value during initialization 
            1   Resets the job structure to the default values
            2   Resets the job structure to the currently active zone settings
        """
        msg = [14, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_JOB_STRUCT_structure_format()
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_dict = self.LASGO_JOB_STRUCT_todict(data_recv)
        return data_dict
    #Block dealing with LASGO_GET_JOB_STRUCT*****************************************

    #Block dealing with LASGO_SET_JOB_STRUCT*****************************************
    def set_LASGO_SET_JOB_STRUCT(self, msg_id, data_dict):
        """
        Wrapper function to set job structure
        """
        msg = [15, msg_id, 0, 0, 0]
        data_list = self.LASGO_JOB_STRUCT_tolist(data_dict)
        s_struct, packer = self.LASGO_JOB_STRUCT_structure_format()
        packed_data, values = self.pack_data(packer, data_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Could not set job struct")
        return msg_recv[3]
    #Block dealing with LASGO_SET_JOB_STRUCT*****************************************

    #Block dealing with LASGO_GET_ZONE_STRUCT*****************************************
    def LASGO_ZONE_STRUCT_structure_format(self):
        """
        Returns a zone structure
        """
        s_struct  = "<"
        s_struct += "I "   #magic;				        Magic ID to validate entry			
        s_struct += "I "   #version;				    Version of this structure			
        s_struct += "I I " #ZONE *prev, *next;	        Next and previous in a linked list	
        s_struct += "80s " #char id[80];				ID of this queue entry			
        s_struct += "I "   #inactive;	    		    Should this one be skipped		
        s_struct += "I "   #LASER laser;		        Which laser to use				
        s_struct += "I "   #SCAN_TYPE scan;		        Type of scan motion				
        s_struct += "d "   #power;	        			Requested power (multiple units)
        s_struct += "I "   #POWER_UNITS units;		    Units of the power (energy.h)	
        s_struct += "I "   #skew;   				    Power constant or skewing on zone	
        s_struct += "d "   #power_skew;			        End power in a skew		
        s_struct += "d "   #velocity;			        Velocity in mm/s for fast scan axis	
        s_struct += "d "   #dwell;				        Dwell in us				
        s_struct += "d "   #track;				        Track spacing (um)				
        s_struct += "I "   #delay_bool #NEW
        s_struct += "I "   #delay_ms   #NEW
        s_struct += "d "   #xmin                        Rectangular area				
        s_struct += "d "   #xmax                        Rectangular area				
        s_struct += "d "   #ymin                        Rectangular area					
        s_struct += "d "   #ymax                        Rectangular area					
        s_struct += "I "   #repeat;				        Number of times to repeat same zone	

        """
        NOTES:
        units:
                RAW = 0,
                WATTS = 1,
                WCM = 2,
                KWMM2 = 3
        scan type:
                UNI_LEFT_RIGHT=0,               Unidirectional left to right
	        UNI_RIGHT_LEFT=1,               Unidirectional right to left
	        UNI_BOTTOM_TOP=2,               Unidirectional bottom to top
	        UNI_TOP_BOTTOM=3,               Unidirectional top to bottom
	        BI_LEFT_RIGHT=4,                Bidirectional  left to right
	        BI_BOTTOM_TOP=5,                Bidirectional  bottom to top
	        ROTARY_SCAN_X=6,                Rotary stage scanning in X
	        ROTARY_SCAN_Y=7	                Rotary stage scanning in Y
        laser:
                CO2=0,	                        Use the CO2 laser
	        LD=1                            Use the laser diode
        """
        return s_struct, struct.Struct(s_struct)

    def units_to_string(self, units_index):
        """
        Returns string of power units index
        """
        options = range(4)
        if units_index not in options:
            self.logger.error("Invalid power index")
            return None
        if     units_index == 0:
               units_string = "RAW"
        elif   units_index == 1:
               units_string = "WATTS"
        elif   units_index == 2:
               units_string = "W/CM"
        elif   units_index == 3:
               units_string = "kW/MM2"
        return units_string

    def units_to_index(self, units_string):
        """
        Returns string of units index from string
        """
        units_index = None
        if     units_string == "RAW":
               units_index = 0
        elif   units_string == "WATTS":
               units_index = 1
        elif   units_string == "W/CM":
               units_index = 2
        elif   units_string == "kW/MM2":
               units_index = 3
        return units_index

    def laser_to_string(self, laser_index):
        """
        Returns string of laser index
        """
        options = range(2)
        if laser_index not in options:
            self.logger.error("Invalid laser index")
            return None
        if     laser_index == 0:
               laser_string = "CO2"
        elif   laser_index == 1:
               laser_string = "LD"
        return laser_string

    def laser_to_index(self, laser_string):
        """
        Returns index of laser string
        """
        laser_index = None
        if     laser_string == "CO2":
               laser_index = 0
        elif   laser_string == "LD":
               laser_index = 1
        return laser_index

    def scan_to_string(self, scan_index):
        """
        Returns string of scan index
        """
        options = range(8)
        if scan_index not in options:
            self.logger.error("Invalid scan index")
            return None
        if   scan_index == 0:
             scan_string = "UNI_LR"
        elif scan_index == 1:
             scan_string = "UNI_RL"
        elif scan_index == 2:
             scan_string = "UNI_BT"
        elif scan_index == 3:
             scan_string = "UNI_TB"
        elif scan_index == 4:
             scan_string = "BI_LR"
        elif scan_index == 5:
             scan_string = "BI_RL"
        elif scan_index == 6:
             scan_string = "ROTARY_X"
        elif scan_index == 7:
             scan_string = "ROTARY_Y"
        return scan_string

    def scan_to_index(self, scan_string):
        """
        Returns index of scan string
        """
        scan_index = None
        if      scan_string == "UNI_LR":
                scan_index = 0
        elif    scan_string == "UNI_RL":
                scan_index = 1
        elif    scan_string == "UNI_BT":
                scan_index = 2
        elif    scan_string == "UNI_TB":
                scan_index = 3
        elif    scan_string == "BI_LR":
                scan_index = 4
        elif    scan_string == "BI_RL":
                scan_index = 5
        elif    scan_string == "ROTARY_X":
                scan_index = 6
        elif    scan_string == "ROTARY_Y":
                scan_index = 7
        return scan_index

    def export_zone_strings(self, zone_dict):
        """
        Returns a zone dictionary where the relevant entries in the zone dictionaries are converted into strings
        Required for writing zone files
        """
        zone_dict_strings = cp.deepcopy(zone_dict)
        zone_dict_strings["Scan"]  = self.scan_to_string (zone_dict_strings["Scan"])
        zone_dict_strings["Units"] = self.units_to_string(zone_dict_strings["Units"])
        zone_dict_strings["Laser"] = self.laser_to_string(zone_dict_strings["Laser"])
        return zone_dict_strings

    def import_zone_indexes(self, zone_dict):
        """
        Returns a zone dictionary where the relevant entries in the zone dictionaries are converted into indexes
        Required for sending read zone files to the LasGo srver
        """
        zone_dict_indexes = cp.deepcopy(zone_dict)
        zone_dict_indexes["Scan"]  = self.scan_to_index (zone_dict_indexes["Scan"])
        zone_dict_indexes["Units"] = self.units_to_index(zone_dict_indexes["Units"])
        zone_dict_indexes["Laser"] = self.laser_to_index(zone_dict_indexes["Laser"])
        return zone_dict_indexes
    
    def LASGO_ZONE_STRUCT_todict(self, data_list):
        """
        Returns a data dictionary from a zone structure list
        """
        data_dict = {}
        data_dict["magic"]         = data_list[0]
        data_dict["version"]       = data_list[1]
        data_dict["prev"]          = data_list[2]
        data_dict["next"]          = data_list[3]
        data_dict["ID"]            = data_list[4].decode('utf-8', errors = "ignore").split('\x00', 1)[0]
        data_dict["Inactive"]      = data_list[5] 
        data_dict["Laser"]         = data_list[6]
        data_dict["Scan"]          = data_list[7]
        data_dict["Power"]         = data_list[8]
        data_dict["Units"]         = data_list[9]
        data_dict["Skew"]          = data_list[10] 
        data_dict["Power_Skew"]    = data_list[11]
        data_dict["Velocity"]      = data_list[12]
        data_dict["Dwell"]         = data_list[13]
        data_dict["Track_Spacing"] = data_list[14]
        data_dict["UseDelay"]      = data_list[15]    #delay_bool #NEW
        data_dict["DelayMS"]       = data_list[16]    #delay_ms   #NEW
        data_dict["Xmin"]          = data_list[17]
        data_dict["Xmax"]          = data_list[18]
        data_dict["Ymin"]          = data_list[19]
        data_dict["Ymax"]          = data_list[20]
        data_dict["Repeat"]        = data_list[21]
        return data_dict

    def LASGO_ZONE_STRUCT_tolist(self, data_dict):
        """
        Returns a data list from a zone structure dict
        """
        data_list = []
        print(data_dict)
        data_list.append(data_dict["magic"])      
        data_list.append(data_dict["version"])    
        data_list.append(data_dict["prev"])       
        data_list.append(data_dict["next"])       
        data_list.append(data_dict["ID"].encode('utf-8'))
        data_list.append(data_dict["Inactive"])  
        data_list.append(data_dict["Laser"])	    
        data_list.append(data_dict["Scan"])      
        data_list.append(data_dict["Power"])	    
        data_list.append(data_dict["Units"])     
        data_list.append(data_dict["Skew"])	    
        data_list.append(data_dict["Power_Skew"])
        data_list.append(data_dict["Velocity"])  
        data_list.append(data_dict["Dwell"])	    
        data_list.append(data_dict["Track_Spacing"])     
        data_list.append(data_dict["UseDelay"])    #delay_bool #NEW
        data_list.append(data_dict["DelayMS"])    #delay_ms   #NEW
        data_list.append(data_dict["Xmin"])      
        data_list.append(data_dict["Xmax"])      
        data_list.append(data_dict["Ymin"])      
        data_list.append(data_dict["Ymax"])      
        data_list.append(data_dict["Repeat"])   
        return data_list

    def get_LASGO_GET_ZONE_STRUCT(self, msg_id):
        """
        Wrapper function to get LASGO_GET_ZONE_STRUCT
        """
        msg = [16, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.LASGO_ZONE_STRUCT_structure_format()
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_dict = self.LASGO_ZONE_STRUCT_todict(data_recv)
        return data_dict
    #Block dealing with LASGO_GET_ZONE_STRUCT*****************************************

    def set_LASGO_VALIDATE_ZONE_SCAN(self, msg_id, option, data_dict):
        """
        Wrapper function to validate a zone scan
        """
        msg = [17, msg_id, int(option), 0, 0]
        data_list = self.LASGO_ZONE_STRUCT_tolist(data_dict)
        s_struct, packer = self.LASGO_ZONE_STRUCT_structure_format()
        packed_data, values = self.pack_data(packer, data_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Could not set job struct")
        return msg_recv[3]

    def set_LASGO_EXECUTE_ZONE_SCAN(self, msg_id, option, data_dict_list, timeout = None):
        """
        Wrapper function to execute a zone scan
        If the scan is a very long one, the socket has to block until the data
        is retrieved. Currently, we block the socket completely for timeout
        seconds, and reset the timeaout to the previous value after completion.
        Eventually, this behavior will change to non-blocking sockets, and
        waiting for a response when data is available.

        option:
            - numbers from 0 to 2**16 will run n-option zones synchronously. Will await that many zone structures
            - adding 2**16 will lead to asynchronous execution of those scans
        """
        if timeout != None:
            current_timeout = self.sock.gettimeout()
            self.sock.settimeout(timeout)
        msg = [18, msg_id, int(option), 0, 0]
        s_struct_all = "<"
        data_list_all = []
        s_struct, packer = self.LASGO_ZONE_STRUCT_structure_format()
        for data_dict in data_dict_list:
            data_list_all.extend(self.LASGO_ZONE_STRUCT_tolist(data_dict))
            s_struct_all += s_struct[1:]
        packer_all = struct.Struct(s_struct_all)
        packed_data, values = self.pack_data(packer_all, data_list_all)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer_all.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Invalid ZONE structure")
        elif int(msg_recv[3]) == 1:
            self.logger.error("Unable to verify the HeatBeatRunDlg")
        elif int(msg_recv[3]) == 2:
            self.logger.error("Unable to verify the watch dog timer thread")
        elif int(msg_recv[3]) == 3:
            self.logger.error("CheckZonePauseAbort() returned true")
        elif int(msg_recv[3]) == 4:
            self.logger.error("Error from RunZone")
        if timeout != None:
            self.sock.settimeout(current_timeout)
        return msg_recv[3]

    def get_LASGO_QUERY_STATUS(self, msg_id):
        """
        Returns current queue status
        """
        msg = [19, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Status %d", msg_recv[3])
            #queue_status = rc & 0xFFFF             /* Extract lower word as queue status
            #system_status = (rc << 16) & 0xFFFF    /* Extract upper word as system status
            #define QUEUE_RUNNING       (0x0001)    /* Queue is cleared to run 
            #define QUEUE_JOB_RUNNING   (0x0002)    /* Job is running         
            #define QUEUE_ZONE_RUNNING  (0x0004)    /* Zone is running       
            #define QUEUE_PAUSE_ZONE    (0x0008)    /* Pause zone until released 
            #define QUEUE_PAUSE_JOB     (0x0010)    /* Pause job until released 
            #define QUEUE_ABORT_ZONE    (0x0020)    /* Abort the current zone
            #define QUEUE_ABORT_JOB     (0x0040)    /* Abort the current job   
            #define QUEUE_ROTARY_ENABLED(0x0080)    /* Rotary stage is enabled
            #define QUEUE_STOPPED       (0x0100)    /* Queue is not running
            #define SYSTEM_LD_FAULT     (0x0100)    /* Laser diode fault state              */
        rc = msg_recv[3]
        queue_status = hex(rc & 0xFFFF)
        system_status = hex((rc << 16) & 0xFFFF)
        #Safe exit is queue = 0x0100, system = 0x0000 (in int is 256, 0)
        #Return dictionary of stastus
        status = {}
        status["queue"] = int(queue_status, 16)
        status["system"] = int(system_status, 16)
        return status

    def option_LASGO_EXECUTE_ZONE_SCAN(self, nzones, asynchronous):
        """
        Returns the correct option integer based on nzones and asynchronous
        """
        option = cp.deepcopy(nzones)
        if asynchronous != 0:
            option = nzones + 2**16
        return option

    def get_position(self):
        """
        Wrapper function to return position, for backwards compatibility with
        text protocol
        Returns the current position of the stage in user coordinates.
        """
        msg_id = 101
        cordsys = 1
        poscur = self.get_LASGO_GET_POSN(msg_id, cordsys)
        return poscur

    def moveto_safe(self, pos):
        """
        Wrapper to move position, and check it the move was successful
        Will return 0 if successful, 1 otherwise
        Implemented here for compatibility
        """
        tol = 0.0015
        msg_id = 101
        cordsys = 1 #User coordinate
        self.set_LASGO_MOVE_TO(msg_id, cordsys, pos)
        poscur = self.get_LASGO_GET_POSN(msg_id, cordsys)
        diff = np.linalg.norm(np.array(pos)-np.array(poscur))
        self.logger.debug("Movement precision %f", diff)
        if diff > tol:
            self.logger.warning("The stage movement not at required precision %f", diff)
            return 1
        else:
            return 0

    def moveto_safer(self, msg_id, pos):
        """
        Wrapper to move position, and check it the move was successful
        Will return 0 if successful, 1 otherwise
        """
        tol = 0.0015
        cordsys = 1 #User coordinate
        self.set_LASGO_MOVE_TO(msg_id, cordsys, pos)
        poscur = self.get_LASGO_GET_POSN(msg_id, cordsys)
        diff = np.linalg.norm(np.array(pos)-np.array(poscur))
        self.logger.debug("Movement precision %f", diff)
        if diff > tol:
            self.logger.warning("The stage movement not at required precision %f", diff)
            return 1
        else:
            return 0

    def execute_LSA_zone_at(self, msg_id, pos, length, power, dwell, id = None):
        """
        Wrapper to perform a single LSA stripe.
        The actions are:
            - get the current zone setting
            - update the zone settings to run a stripe at 
                xmin = pos[0]
                ymin = pos[1]
                xmax = pos[0]
                ymax = pos[1] + length
            - update the zone settings to the new power
            - update the zone settings to the new dwell
            - update ID of the zone (if supplied)
            - execute the zone
        Will return the new, executed zone
        """
        current_zone = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
        zone = cp.deepcopy(current_zone)
        zone["xmin"] =  float(pos[0])
        zone["xmax"] =  float(pos[0])
        zone["ymin"] =  float(pos[1])
        zone["ymax"] =  float(pos[1]) + float(length)
        zone["power"] = float(power)
        zone["dwell"] = float(dwell)
        if id != None: zone["id"] = id
        option = 1
        res = lasgo_client.set_LASGO_EXECUTE_ZONE_SCAN(msg_id + 1, option, zone)
        if res != 0:
            self.logger.error("Execution of LSA stripe failed")
        return zone

class ClientDCXProtocol(ClientStructProtocol):
    """
    Subclass with functions implemented specifically for the DCX camera.
    Relies on the ClientStructProtocol class.
    """
    def __init__(self, connect = True, address = None, port = None):
        super(ClientDCXProtocol, self).__init__()
        self.logger = logging.getLogger("ClientDCX")
        self.rotate = None
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "camera" 
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1

    #Block dealing with DCX_GET_CAMERA_INFO*****************************************
    def DCX_GET_CAMERA_INFO_structure_format(self):
        """
        Returns structure format of the camera info.
        """
        s_struct  = "<"
        s_struct += "32s " #Camera manufacturer
        s_struct += "32s " #Camera model
        s_struct += "32s " #Camera serial number
        s_struct += "32s " #Camera version
        s_struct += "32s " #Firmware date
        s_struct += "I "   #Camera ID (as set in EEPROM)
        s_struct += "I "   #Monochrome or color mode, bool??
        s_struct += "I "   #Pixel pitch in um */
        s_struct += "d "   #Frame rate (frames per second) */
        s_struct += "d "   #Current exposure (ms) */
        s_struct += "d "   #Gamma value */
        s_struct += "I "   #Gains in non-linear range [0,100] */
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto */
        s_struct += "d"    #color_correction_factor;
        return s_struct, struct.Struct(s_struct)

    def DCX_GET_CAMERA_INFO_todict(self, data_list):
        """
        Transform list to dictionary of DCX_GET_CAMERA_INFO structure
        """
        data_dict = {}
        data_dict['manufacturer']      = data_list[0].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera manufacturer 
        data_dict['model']             = data_list[1].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera model 
        data_dict['serial']            = data_list[2].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera serial number
        data_dict['version']           = data_list[3].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera version
        data_dict['date']              = data_list[4].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Firmware date
        data_dict['CameraID']          = data_list[5]  #Camera ID (as set in EEPROM)
        data_dict['color_mode']        = data_list[6]  #Monochrome or color mode
        data_dict['pixel_pitch']       = data_list[7]  #Pixel pitch in um 
        data_dict['fps']               = data_list[8]  #Frame rate (fps)
        data_dict['exposure']          = data_list[9]  #Current exposure (ms) */
        data_dict['gamma']             = data_list[10] #Gamma value */
        data_dict['master_gain']       = data_list[11] #Gains in non-linear range [0,100] */
        data_dict['red_gain']          = data_list[12] #red_gain, green_gain, blue_gain;
        data_dict['green_gain']        = data_list[13] #red_gain, green_gain, blue_gain;
        data_dict['blue_gain']         = data_list[14] #red_gain, green_gain, blue_gain;
        data_dict['color_correction']  = data_list[15] #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto */
        data_dict['correction_factor'] = data_list[16] #color_correction_factor;
        return data_dict

    def get_DCX_GET_CAMERA_INFO(self, msg_id):
        """
        Wrapper function to get camera info.
        """
        msg = [2, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.DCX_GET_CAMERA_INFO_structure_format()
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_recv_dict = self.DCX_GET_CAMERA_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with DCX_GET_CAMERA_INFO*****************************************

    #Block dealing with DCX_GET_IMAGE_INFO******************************************
    def DCX_GET_IMAGE_INFO_structure_format(self):
        """
        Returns structure format of the image info.
        """
        s_struct  = "<"
        s_struct += "I "   #image width and height 
        s_struct += "I "   #image width and height 
        s_struct += "I "   #Bytes between each row (allocate pitch*height)
        s_struct += "d "   #Current exposure (ms) 
        s_struct += "d "   #Gamma value 
        s_struct += "I "   #Gains in non-linear range [0,100] 
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #red_gain, green_gain, blue_gain;
        s_struct += "I "   #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto */
        s_struct += "d"    #color_correction_factor;
        s_struct += "I "   #Number saturated pixels red_saturate, green_saturate, blue_saturate
        s_struct += "I "   #Number saturated pixels red_saturate, green_saturate, blue_saturate
        s_struct += "I "   #Number saturated pixels red_saturate, green_saturate, blue_saturate
        return s_struct, struct.Struct(s_struct)

    def DCX_GET_IMAGE_INFO_todict(self, data_list):
        """
        Transform list to dictionary of DCX_GET_IMAGE_INFO structure.
        """
        data_dict = {}
        data_dict['width']                   =  data_list[0]  #image width and height 
        data_dict['height']                  =  data_list[1]  #image width and height 
        data_dict['memory_pitch']            =  data_list[2]  #Bytes between each row (allocate pitch*height)
        data_dict['exposure']                =  data_list[3]  #Current exposure (ms) 
        data_dict['gamma']                   =  data_list[4]  #Gamma value 
        data_dict['master_gain']             =  data_list[5]  #Gains in non-linear range [0,100] 
        data_dict['red_gain']                =  data_list[6]  #red_gain, green_gain, blue_gain;
        data_dict['green_gain']              =  data_list[7]  #red_gain, green_gain, blue_gain;
        data_dict['blue_gain']               =  data_list[8]  #red_gain, green_gain, blue_gain;
        data_dict['color_correction']        =  data_list[9]  #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto */
        data_dict['color_correction_factor'] =  data_list[10] #color_correction_factor;
        data_dict['red_saturate']            =  data_list[11] #Number saturated pixels red_saturate, green_saturate, blue_saturate
        data_dict['green_saturate']          =  data_list[12] #Number saturated pixels red_saturate, green_saturate, blue_saturate
        data_dict['blue_saturate']           =  data_list[13] #Number saturated pixels red_saturate, green_saturate, blue_saturate
        return data_dict

    def get_DCX_GET_IMAGE_INFO(self, msg_id):
        """
        Wrapper function to get image info.
        """
        msg = [4, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.DCX_GET_IMAGE_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.DCX_GET_IMAGE_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with DCX_GET_IMAGE_INFO******************************************

    #Block dealing with DCX_GET_CURRENT_IMAGE******************************************
    def DCX_GET_CURRENT_IMAGE_structure_format(self, data_size):
        """
        Returns structure format of the image data.
        """
        s_struct  = "<"
        s_struct += str(data_size)+"B "
        return s_struct, struct.Struct(s_struct)

    def get_DCX_GET_CURRENT_IMAGE(self, msg_id, image_info):
        """
        Wrapper function to get image data.
        """
        msg = [5, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        data_size = msg_recv[4]
        s_struct, unpacker = self.DCX_GET_CURRENT_IMAGE_structure_format(data_size)
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
    #Print some parts of the data
    #    for i in range(10):
    #        str_out = "Row "+str(i)
    #        for j in range(15):
    #            str_out += " "+str(data_recv[i*image_info['memory_pitch']+j]).zfill(3)
    #        print(str_out)
        self.logger.debug("Image data received, %d", data_size)
        return data_recv 
    #Block dealing with DCX_GET_CURRENT_IMAGE******************************************

    #Block dealing with DCX_SET_EXPOSURE********************************************
    #DEPRECATED
    def DCX_SET_EXPOSURE_structure_format(self):
        """
        Returns structure format for setting exposure.
        """
        s_struct  = "<"
        s_struct += "d " # Exposure time in ms
        return s_struct, struct.Struct(s_struct)

    def set_DCX_SET_EXPOSURE(self, msg_id, exposure):
        """
        Wrapper function to set exposure.
        """
        msg = [6, msg_id, 0, 0, 0] #Command index is 6, length of the subsequently sent data is 8
        # Prepare settings data
        s_struct, packer = self.DCX_SET_EXPOSURE_structure_format()
        packed_data, values = self.pack_data(packer, [exposure])
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set exposure")
        return 
    #Block dealing with DCX_SET_EXPOSURE********************************************

    #Block dealing with DCX_GET_EXPOSURE_PARMS********************************************
    def EXPOSURE_PARMS_dict(self): 
        """
        Returns exposure setting dict. Initialized to False
        """
        exposure_dict = {}
        exposure_dict["EXPOSURE"]    = True
        exposure_dict["FPS"]         = True
        exposure_dict["GAMMA"]       = True
        exposure_dict["MASTER_GAIN"] = True
        exposure_dict["RED_GAIN"]    = True
        exposure_dict["GREEN_GAIN"]  = True
        exposure_dict["BLUE_GAIN"]   = True
        return exposure_dict

    def EXPOSURE_PARMS_opt_to_bin(self, exposure_dict):
        """
        Converts exposure dictionary to correct bites
        exposure_dict is a dictionary of logicals, determining which parameters
        to modify
        # Set one or more image capture parms / returns current values (structures both) */
        # Or'd bit-flags in option to control setting parameters */
        # Exposure always has priority over FPS, but FPS will be maximized if not modified with exposure */
                #define DCXF_MODIFY_EXPOSURE     (0x01)   /* Modify exposure (value in ms) */
                #define DCXF_MODIFY_FPS          (0x02)   /* Modify frames per second */
                #define DCXF_MODIFY_GAMMA        (0x04)   /* Modify gamma */
                #define DCXF_MODIFY_MASTER_GAIN  (0x08)   /* Modify master gain */
                #define DCXF_MODIFY_RED_GAIN     (0x10)   /* Red channel gain */
                #define DCXF_MODIFY_GREEN_GAIN   (0x20)   /* Green channel gain */
                #define DCXF_MODIFY_BLUE_GAIN    (0x40)   /* Blue channel gain */
        """
        option = 0
        if exposure_dict["EXPOSURE"]   : option += int("01", 16)
        if exposure_dict["FPS"]        : option += int("02", 16)
        if exposure_dict["GAMMA"]      : option += int("04", 16)
        if exposure_dict["MASTER_GAIN"]: option += int("08", 16)
        if exposure_dict["RED_GAIN"]   : option += int("10", 16)
        if exposure_dict["GREEN_GAIN"] : option += int("20", 16)
        if exposure_dict["BLUE_GAIN"]  : option += int("40", 16)
        return option

    def EXPOSURE_PARMS_bin_to_opt(self, option):
        """
        Converts exposure integer to dictionary
        """
        exposure_dict = {}
        exposure_dict["EXPOSURE"]    = True if option & 0b0000001 else False
        exposure_dict["FPS"]         = True if option & 0b0000010 else False
        exposure_dict["GAMMA"]       = True if option & 0b0000100 else False
        exposure_dict["MASTER_GAIN"] = True if option & 0b0001000 else False
        exposure_dict["RED_GAIN"]    = True if option & 0b0010000 else False
        exposure_dict["GREEN_GAIN"]  = True if option & 0b0100000 else False
        exposure_dict["BLUE_GAIN"]   = True if option & 0b1000000 else False
        return exposure_dict

    def EXPOSURE_PARMS_todict(self, data_list):
        """
        Transform list to dictionary of EXPOSURE_PARMS structure.
        """
        data_dict = {}
        data_dict["EXPOSURE"]      =  data_list[0] 
        data_dict["FPS"]           =  data_list[1] 
        data_dict["GAMMA"]         =  data_list[2] 
        data_dict["MASTER_GAIN"]   =  data_list[3] 
        data_dict["RED_GAIN"]      =  data_list[4] 
        data_dict["GREEN_GAIN"]    =  data_list[5] 
        data_dict["BLUE_GAIN"]     =  data_list[6] 
        return data_dict

    def EXPOSURE_PARMS_tolist(self, data_dict):
        """
        Transform dictionary to list of EXPOSURE_PARMS structure.
        """
        data_list = []
        data_list.append(data_dict["EXPOSURE"]   )
        data_list.append(data_dict["FPS"]        )
        data_list.append(data_dict["GAMMA"]      )
        data_list.append(data_dict["MASTER_GAIN"])
        data_list.append(data_dict["RED_GAIN"]   )
        data_list.append(data_dict["GREEN_GAIN"] )
        data_list.append(data_dict["BLUE_GAIN"]  )
        return data_list

    def EXPOSURE_PARMS_structure_format(self):
        """
        Returns structure format to set params
        /* Structure used by DCX_CLIENT to allow changes to exposure */
        """
        s_struct  = "<"
        s_struct += "d "  # double exposure;                         /* Exposure time in ms           
        s_struct += "d "  # double fps;                              /* Frame rate (per second)       
        s_struct += "I "  # uint32_t gamma;                          /* Gamma value (0 < gamma < 100) 
        s_struct += "I "  # uint32_t master_gain;                    /* Master gain (0 < gain < 100)  
        s_struct += "3I " # uint32_t red_gain, green_gain, blue_gain;/* Individual channel gains      
        return s_struct, struct.Struct(s_struct)

    def get_DCX_GET_EXPOSURE_PARMS(self, msg_id):
        """
        Wrapper function to get exposure params
        """
        msg = [6, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.EXPOSURE_PARMS_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.EXPOSURE_PARMS_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with DCX_GET_EXPOSURE_PARMS********************************************

    #Block dealing with DCX_SET_GAINS***********************************************
    #DEPRECATED
    def DCX_SET_GAINS_structure_format(self):
        """
        Returns structure format to set gains.
        """
        s_struct  = "<"
        s_struct += "I " # Master Gains in non-linear range [0,100] 
        s_struct += "I " # Red    Gains in non-linear range [0,100] 
        s_struct += "I " # Green  Gains in non-linear range [0,100] 
        s_struct += "I " # Blue   Gains in non-linear range [0,100] 
        return s_struct, struct.Struct(s_struct)

    def set_DCX_SET_GAINS(self, msg_id, gains):
        """
        Wrapper function to set exposure.
        """
        if(len(gains) != 4):
            self.logger.error("A total of 4 integer values must be submitted to set gains.")
            #If we are dealing with a monochrome cam, the latter 3
            #entries will be ignored by the server
        # Send comm data
        msg = [7, msg_id, 0, 0, 0] #Command index is 7, length of the subsequently sent data is 16, important
        # Prepare settings data
        s_struct, packer = self.DCX_SET_GAINS_structure_format()
        msg[4] = packer.size
        packed_data, values = self.pack_data(packer,gains)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set exposure")
        return 
    #Block dealing with DCX_SET_GAINS***********************************************

    #Block dealing with DCX_SET_EXPOSURE_PARMS********************************************
    def set_DCX_SET_EXPOSURE_PARMS(self, msg_id, exposure_dict, params_to_set = None):
        """
        Wrapper function to set exposure.
        """
        # Send comm data
        msg = [7, msg_id, 0, 0, 0] #Command index is 7, length of the subsequently sent data is 16, important
        #Which parameters to set
        if params_to_set is None:
            params_to_set = self.EXPOSURE_PARMS_dict()
        set_option = self.EXPOSURE_PARMS_opt_to_bin(params_to_set)
        print("Exposure params and option", set_option, exposure_dict)
        msg[2] = set_option
        # Prepare settings data, the real parameters
        s_struct, packer = self.EXPOSURE_PARMS_structure_format()
        msg[4] = packer.size
        exposure_list = self.EXPOSURE_PARMS_tolist(exposure_dict)
        packed_data, values = self.pack_data(packer, exposure_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set exposure")
        s_struct, unpacker = self.EXPOSURE_PARMS_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.EXPOSURE_PARMS_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv
    #Block dealing with DCX_SET_EXPOSURE_PARMS********************************************

    def get_DCX_QUERY_VERSION(self, msg_id):
        """
        Returns version of the camera server.
        """
        msg = [1, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Server version %d", msg_recv[3])
        return msg_recv[3]

    def get_DCX_ACQUIRE_IMAGE(self, msg_id):
        """
        Captures an image with given settings.
        """
        msg = [3, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return 

    #Block dealing with DCX_RING_INFO********************************************
    def DCX_RING_INFO_structure_format(self):
        """
        Returns structure format for getting ring info
        """
        s_struct  = "<"
        s_struct += "I " # Number of buffers in the ring
        s_struct += "I " # Number of frames valid since last reset
        s_struct += "I " # index of last buffer used (from events)
        s_struct += "I " # index of currently displayed frame
        return s_struct, struct.Struct(s_struct)

    def DCX_RING_INFO_todict(self, data_list):
        """
        Transform list to dictionary of DCX_RING_INFO_structure_format
        """
        data_dict = {}
        data_dict['nSize']                 =  data_list[0]  # Number of buffers in the ring
        data_dict['nValid']                =  data_list[1]  # Number of frames valid since last reset
        data_dict['iLast']                 =  data_list[2]  # index of last buffer used (from events)
        data_dict['iShow']                 =  data_list[3]  # index of currently displayed frame
        return data_dict

    def get_DCX_RING_INFO(self, msg_id):
        """
        Wrapper function to get ring info
        """
        msg = [8, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.DCX_RING_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.DCX_RING_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with DCX_RING_INFO********************************************

    #Block dealing with DCX_RING_GET_SIZE********************************************
    def get_DCX_RING_GET_SIZE(self, msg_id):
        """
        Return current number of buffers (maximum frames) in the ring
        """
        msg = [9, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Ring size %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_RING_GET_SIZE********************************************

    #Block dealing with DCX_RING_SET_SIZE********************************************
    def set_DCX_RING_SET_SIZE(self, msg_id, ring_size):
        """
        Return current number of buffers (maximum frames) in the ring
        """
        msg = [10, msg_id, 0, 0, 0]
        msg[2] = ring_size
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Ring size set %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_RING_SET_SIZE********************************************
    
    #Block dealing with DCX_RING_GET_FRAME_CNT********************************************
    def get_DCX_RING_GET_FRAME_CNT(self, msg_id):
        """
        Returns the number of frames in ring that are active
        """
        msg = [11, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Number of frames in ring %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_RING_GET_FRAME_CNT********************************************

    #Block dealing with DCX_RING_IMAGE_N_DATA******************************************
    def HEAD_DCX_RING_IMAGE_N_DATA_structure_format(self):
        """
        Returns structure format of the image n data
        """
        s_struct  = "<"
        s_struct += "d " # Time of image (seconds w/ ms resolution) 
        s_struct += "I " # width
        s_struct += "I " # height
        s_struct += "I " # pitch
        return s_struct, struct.Struct(s_struct)

    def DCX_RING_IMAGE_N_DATA_structure_format(self, data_size):
        """
        Returns structure format of the image n data
        """
        s_struct  = "<"
        s_struct += "d " # Time of image (seconds w/ ms resolution) 
        s_struct += "I " # width
        s_struct += "I " # height
        s_struct += "I " # pitch
        s_struct += str(data_size)+"B " #width x height data immediately follows
        return s_struct, struct.Struct(s_struct)

    def get_DCX_RING_IMAGE_N_DATA(self, msg_id, n_data):
        """
        Return image data for frame buffer N (option) 
        """
        msg = [12, msg_id, 0, 0, 0]
        msg[2] = n_data
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        data_size = msg_recv[4]

        #Split image data into head and image data
        head_s_struct, head_unpacker = self.HEAD_DCX_RING_IMAGE_N_DATA_structure_format()
        head_size = head_unpacker.size
        img_size = data_size - head_size

        #The complete data
        s_struct, unpacker = self.DCX_RING_IMAGE_N_DATA_structure_format(img_size)
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        self.logger.debug("Image data received, %d", data_size)

        #Unpack the header data
        data_dict = {}
        data_dict["timestamp"] = data_recv[0]
        data_dict["width"]     = data_recv[1]
        data_dict["height"]    = data_recv[2]
        data_dict["pitch"]     = data_recv[3]
        print(data_dict)
        image_data = data_recv[4:]
        if data_dict["pitch"] == data_dict["width"]: 
            image_data = np.uint8(image_data).reshape((data_dict["height"], data_dict["pitch"])) #packed_data
        #In this case we are dealing with a monochrome image, but we should be careful. 
        #Might have to get the info from camera itself and not the image 
            img = Image.fromarray(image_data, 'L')
        elif data_dict["pitch"] == 3 * data_dict["width"]: 
        #If it is an BGR image, we have to change it into RGB
            image_data = np.uint8(image_data).reshape( (data_dict["height"], data_dict["width"], 3)) #packed_data
            img = Image.fromarray(image_data, 'RGB')
            b, g, r = img.split()
            img = Image.merge("RGB", (r, g, b))
        data_dict["img"]       = img
        return data_dict
    #Block dealing with DCX_RING_IMAGE_N_DATA******************************************

    #Block dealing with DCX_BURST_ARM********************************************
    def set_DCX_BURST_ARM(self, msg_id):
        """
        Arm the burst (returns immediately)
        BURST_ARM: 0 if successful (or if already armed)
        """
        msg = [13, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst armed %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_BURST_ARM********************************************

    #Block dealing with DCX_BURST_ABORT********************************************
    def set_DCX_BURST_ABORT(self, msg_id):
        """
        Abort awaiting burst (returns immediately)
        BURST_ABORT: 0 if successful (or wasn't armed)
        """
        msg = [14, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst aborted %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_BURST_ABORT********************************************

    #Block dealing with DCX_BURST_STATUS********************************************
    def get_DCX_BURST_STATUS(self, msg_id):
        """
        Query status of the burst (is it armed, complete, etc.) 
        (0) BURST_STATUS_INIT                       Initial value on program start ... no request ever received
        (1) BURST_STATUS_ARM_REQUEST                An arm request received ... but thread not yet running
        (2) BURST_STATUS_ARMED                      Armed and awaiting a stripe start message
        (3) BURST_STATUS_RUNNING                    In stripe run
        (4) BURST_STATUS_COMPLETE                   Stripe completed with images saved
        (5) BURST_STATUS_ABORT                      Capture was aborted
        (6) BURST_STATUS_FAIL                       Capture failed for other reason (no semaphores, etc.)
        """
        msg = [15, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst status %d", msg_recv[3])
        return msg_recv[3]
        return 
    #Block dealing with DCX_BURST_STATUS********************************************

    #Block dealing with DCX_BURST_WAIT********************************************
    def set_DCX_BURST_WAIT(self, msg_id, timeout):
        """
        Wait for burst to complete (request.option = msTimeout)
        BURST_WAIT: 0 if complete, 1 on timeout
        """
        msg = [16, msg_id, 0, 0, 0]
        msg[2] = int(timeout) #In ms
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst wait %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_BURST_WAIT********************************************

    #Block dealing with DCX_LED_SET_STATE********************************************
    def set_DCX_LED_SET_STATE(self, msg_id, led_state):
        """
        Set LED current supply either on or off (or query) 
        Option: 0 to turn off
                1 to turn on
                2 to query (same effect for any value not 0 or 1)
        Return value is BOOL:  0 if off, 1 if on. If the state can’t be determined, will return 0 also.
        """
        msg = [17, msg_id, 0, 0, 0]
        msg[2] = led_state
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("LED state %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_LED_SET_STATE********************************************

    #Block dealing with DCX_VIDEO_ENABLE********************************************
    def set_DCX_VIDEO_ENABLE(self, msg_id, led_state):
        """
        Set Videa current supply either on or off (or query) 
        Option: 0 to turn off
                1 to turn on
                2 to query (same effect for any value not 0 or 1)
        Return value is BOOL:  0 if off, 1 if on. If the state can’t be determined, will return 0 also.
        """
        msg = [18, msg_id, 0, 0, 0]
        msg[2] = led_state
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Video state %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_VIDEO_ENABLE********************************************

    #Block dealing with DCX_SAVE_IMAGE_BUFFERS********************************************
    def set_DCX_SAVE_IMAGE_BUFFERS(self, msg_id):
        """
        Save image buffers based on template pathname
        """
        msg = [19, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Buffer saved %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with DCX_SAVE_IMAGE_BUFFERS********************************************

    def get_image(self, msg_id, delay = None):
        """
        Wrapper function to get an image.
        First aquires the image, then gets the image info, and finally sends
        the image itself back to the client.
        Some post-processing is performed to return a PIL image data, which is
        either monochrome or RGB.
        """
        if delay is not None:
            print("Sleeping before acquiring image")
            time.sleep(delay)
        self.get_DCX_ACQUIRE_IMAGE(msg_id)
        if delay is not None:
            print("Sleeping after acquiring image")
            time.sleep(delay)
        image_info = self.get_DCX_GET_IMAGE_INFO(msg_id + 1)
        image_data = self.get_DCX_GET_CURRENT_IMAGE(msg_id + 2, image_info)
        if image_info["memory_pitch"] == image_info["width"]: 
            image_data = np.uint8(image_data).reshape(
                (image_info["height"], image_info["memory_pitch"])) #packed_data
        #In this case we are dealing with a monochrome image, but we should be careful. 
        #Might have to get the info from camera itself and not the image 
            img = Image.fromarray(image_data, 'L')
        elif image_info["memory_pitch"] == 3 * image_info["width"]: 
        #If it is an BGR image, we have to change it into RGB
            image_data = np.uint8(image_data).reshape(
                (image_info["height"], image_info["width"], 3)) #packed_data
            img = Image.fromarray(image_data, 'RGB')
            b, g, r = img.split()
            img = Image.merge("RGB", (r, g, b))
        if self.rotate is not None:
            img = img.rotate(self.rotate, expand=True)
        return img, image_info

class ClientSpecProtocol(ClientStructProtocol):
    """
    Subclass with functions implemented specifically for the Ocean Optics
    spectrometer.
    Relies on the ClientStructProtocol class.
    """
    def __init__(self, connect = True, address = None, port = None):
        super(ClientSpecProtocol, self).__init__()
        self.logger = logging.getLogger("ClientSpec")
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "spec"
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1

    def get_SPEC_QUERY_VERSION(self, msg_id):
        """
        Wrapper function to return spectroscopy server version.
        """
        msg = [1, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        #print("Server version", msg_recv[3])
        return msg_recv[3]

    #Block dealing with SPEC_GET_SPECTROMETER_INFO**********************************
    def SPEC_GET_SPECTROMETER_INFO_structure_format(self):
        """
        Returns structure format of the spectrometer infor
        """
        s_struct  = "<"
        s_struct += "I "   #Spectrometer exists
        s_struct += "32s " #Camera model
        s_struct += "32s " #Camera serial number
        s_struct += "I "   #Number of points in spectrum
        s_struct += "d "   #Min wavelength of spectrometer
        s_struct += "d "   #Max wavelength of spectrometer
        s_struct += "d "   #Integration target
        s_struct += "I "   #Averaging specified
        s_struct += "I "   #use dark pixel
        s_struct += "I "   #use nl correct
        return s_struct, struct.Struct(s_struct)

    def SPEC_GET_SPECTROMETER_INFO_todict(self, data_list):
        """
        Transform list to dictionary of SPEC_GET_SPECTROMETER_INFO structure.
        """
        data_dict = {}
        data_dict['exists']            =  data_list[0]
        data_dict['model']             =  data_list[1].decode('utf-8', errors =
                "ignore").split('\x00', 1)[0]          #model.
        data_dict['serial']            =  data_list[2].decode('utf-8', errors =
                "ignore").split('\x00', 1)[0]          #serial number.
        data_dict['npoints']           =  data_list[3] #Number of points in spectrum
        data_dict['lambda_min']        =  data_list[4] #Min wavelength of spectrometer
        data_dict['lambda_max']        =  data_list[5] #Max wavelength of spectrometer
        data_dict['ms_integrate']      =  data_list[6] #Integration target
        data_dict['num_average']       =  data_list[7] #Averaging specified
        data_dict['use_dark_pixel']    =  data_list[8] #use dark pixel
        data_dict['use_nl_correct']    =  data_list[9] #use nl correct
        return data_dict

    def get_SPEC_GET_SPECTROMETER_INFO(self, msg_id):
        """
        Wrapper function to get spectrometer info.
        """
        msg = [2, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.SPEC_GET_SPECTROMETER_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.SPEC_GET_SPECTROMETER_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with SPEC_GET_SPECTROMETER_INFO**********************************

    #Block dealing with SPEC_GET_WAVELENGTHS****************************************
    def SPEC_GET_WAVELENGTHS_structure_format(self, npoints):
        """
        Returns structure format to get the wavelengths.
        """
        s_struct  = "<"+str(npoints)+"d"   
        return s_struct, struct.Struct(s_struct)

    def get_SPEC_GET_WAVELENGTHS(self, msg_id, spectrometer_info):
        """
        Wrapper function to get spectrometer info.
        """
        msg = [3, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = \
                self.SPEC_GET_WAVELENGTHS_structure_format(spectrometer_info["npoints"])
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        self.logger.debug("Received "+':'.join([str(i) for i in data_recv]))
        return data_recv
    #Block dealing with SPEC_GET_WAVELENGTHS****************************************

    #Block dealing with SPEC_GET_INTEGRATION_PARMS****************************************
    def SPEC_INTEGRATION_PARMS_structure_format(self):
        """
        Returns structure format of SPEC_INTEGRATION_PARMS
        """
        s_struct  = "<"
        s_struct += "d "   #Integration target in ms
        s_struct += "I "   #Averaging specified
        s_struct += "I "   #use dark pixel
        s_struct += "I "   #use nl correct to counts
        return s_struct, struct.Struct(s_struct)

    def SPEC_INTEGRATION_PARMS_todict(self, data_list):
        """
        Transform list to dictionary of SPEC_INTEGRATION_PARMS structure.
        """
        data_dict = {}
        data_dict['ms_integrate']      =  data_list[0] #Integration target
        data_dict['num_average']       =  data_list[1] #Averaging specified
        data_dict['use_dark_pixel']    =  data_list[2] #use dark pixel
        data_dict['use_nl_correct']    =  data_list[3] #use nl correct
        return data_dict

    def SPEC_INTEGRATION_PARMS_tolist(self, data_dict):
        """
        Transform dictionary to list of SPEC_INTEGRATION_PARMS structure.
        """
        data_list = []
        data_list.append(data_dict['ms_integrate']  )  #Integration target
        data_list.append(data_dict['num_average']   )  #Averaging specified
        data_list.append(data_dict['use_dark_pixel'])  #use dark pixel
        data_list.append(data_dict['use_nl_correct'])  #use nl correct
        return data_list

    def get_SPEC_GET_INTEGRATION_PARMS(self, msg_id):
        """
        Wrapper function to get integration info.
        """
        msg = [4, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.SPEC_INTEGRATION_PARMS_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.SPEC_INTEGRATION_PARMS_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict

    def set_SPEC_SET_INTEGRATION_PARMS(self, msg_id, data_dict):
        """
        Wrapper function to set integration info.
        """
        msg = [5, msg_id, 0, 0, 0]
        data_list = self.SPEC_INTEGRATION_PARMS_tolist(data_dict)
        s_struct, packer = self.SPEC_INTEGRATION_PARMS_structure_format()
        packed_data, values = self.pack_data(packer, data_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        msg[4] = packer.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Passed structure has the wrong size")
        elif int(msg_recv[3]) != 0:
            self.logger.error("Passed bad values")
        return msg_recv[3]
    #Block dealing with SPEC_GET_INTEGRATION_PARMS****************************************

    def get_SPEC_ACQUIRE_SPECTRUM(self, msg_id):
        """
        Wrapper function to aquire a spectrum
        """
        msg = [6, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return 
    
    def get_SPEC_ACQUIRE_COMPLETE_SPECTRUM(self, msg_id):
        """
        Wrapper function to aquire a spectrum
        """
        msg = [16, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        #Number of spectra in the file is stored in msg[2]
        return msg_recv[2]
    
    #Block dealing with SPEC_GET_SPECTRUM_INFO**************************************
    def SPEC_GET_SPECTRUM_INFO_structure_format(self):
        """
        Returns structure format for the spectrum info.
        """
        s_struct  = "<"
        s_struct += "I " #number of points in spectrum
        s_struct += "d " #Minimum Wavelength
        s_struct += "d " #Maximum Wavelength
        s_struct += "d " #Integration target
        s_struct += "I " #Averaging specified
        s_struct += "I " #Boolean flg for dark pixel correction
        s_struct += "I " #Boolean flag for non-linear correction
        s_struct += "q " #Integer of the timestamp
        return s_struct, struct.Struct(s_struct)

    def SPEC_GET_SPECTRUM_INFO_todict(self, data_list):
        """
        Transform list to dictionary of SPEC_GET_SPECTRUM_INFO structure.
        """
        data_dict = {}
        data_dict['npoints']        = data_list[0] #number of points in spectrum
        data_dict['lambda_min']     = data_list[1] #Minimum Wavelength
        data_dict['lambda_max']     = data_list[2] #Maximum Wavelength
        data_dict['ms_integrate']   = data_list[3] #Integration target
        data_dict['num_average']    = data_list[4] #Averaging specified
        data_dict['use_dark_pixel'] = data_list[5] #Boolean flg for dark pixel correction
        data_dict['use_nl_correct'] = data_list[6] #Boolean flag for non-linear correction
        data_dict['timestamp']      = data_list[7] #Boolean flag for non-linear correction
        return data_dict

    def get_SPEC_GET_SPECTRUM_INFO(self, msg_id):
        """
        Wrapper function to get spectrum info.
        """
        msg = [7, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        print("MSG", msg_recv)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.SPEC_GET_SPECTRUM_INFO_structure_format()
        print("Unacker", unpacker)
        packed_data = self.sock.recv(unpacker.size)
        print("DATA recv")
        self.check_crc(packed_data, msg_recv)
        print("CRC")
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.SPEC_GET_SPECTRUM_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with SPEC_GET_SPECTRUM_INFO**************************************

    #Block dealing with SPEC_GET_SPECTRUM_DATA**************************************
    def SPEC_GET_SPECTRUM_DATA_structure_format(self, npoints):
        """
        Returns structure format to get the spectrum.
        """
        s_struct  = "<"
        s_struct += str(npoints)+"d "
        return s_struct, struct.Struct(s_struct)

    def get_SPEC_GET_SPECTRUM_DATA(self, msg_id, spectrum_info):
        """
        Wrapper function to get spectrum.
        """
        msg = [8, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if msg_recv[3] == 0:
            s_struct, unpacker = self.SPEC_GET_SPECTRUM_DATA_structure_format(
                    spectrum_info['npoints'])
            data_recv = self.recv_data_buffered(unpacker, msg_recv)
        elif msg_recv[3] == -1:
            self.logger.error("Aquire the spectrum first, %d", msg_id, msg_recv[3])
            data_recv = []
        return data_recv #packed_data

    def get_SPEC_GET_COMPLETE_SPECTRUM_DATA(self, msg_id, spectrum_info, nspect):
        """
        Wrapper function to get spectrum.
        """
        msg = [18, msg_id, 0, 0, 0]
        print("NSPECT", nspect)
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if msg_recv[3] == 0:
            s_struct, unpacker = self.SPEC_GET_SPECTRUM_DATA_structure_format(
                    spectrum_info['npoints'] * nspect)
            data_recv = self.recv_data_buffered(unpacker, msg_recv)
            data_recv = [data_recv[i:i+spectrum_info['npoints']] for i in range(0,len(data_recv),spectrum_info['npoints'])]
        elif msg_recv[3] == -1:
            self.logger.error("Aquire complete spectrum first, %d", msg_id, msg_recv[3])
            data_recv = []
        return data_recv #packed_data
    #Block dealing with SPEC_GET_SPECTRUM_DATA**************************************

    def get_spectrum(self, msg_id):
        """
        Wrapper function to get the spectrum.
        First aquires the spectrum, then gets the spectrum info, 
        and finally gets the spectrum itself.
        """
        self.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
        spec_info = self.get_SPEC_GET_SPECTRUM_INFO(msg_id+1)
        spec_data = self.get_SPEC_GET_SPECTRUM_DATA(msg_id+2, spec_info)
        return spec_data

    def get_wavelengths(self, msg_id):
        """
        Wrapper function to get the wavelengths.
        First gets the spectrum info, 
        then gets the spectrum wavelenths.
        """
        dev_info = self.get_SPEC_GET_SPECTROMETER_INFO(msg_id)
        wl = self.get_SPEC_GET_WAVELENGTHS(msg_id+1, dev_info)
        return wl, dev_info

class ClientFocusProtocol(ClientStructProtocol):
    """
    Subclass with functions implemented specifically for the Focus module.
    Relies on the ClientStructProtocol class.
    """
    def __init__(self, connect = True, address = None, port = None):
        super(ClientFocusProtocol, self).__init__()
        self.logger = logging.getLogger("ClientFocus")
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "focus"
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1

    def grid_to_pts(self, grid):
        """
        Grabs the number of points given a grid
            WAFER_9PT       (0) Circular wafer pattern grids
            WAFER_25PT      (1) Make sure matches focus.h TESS_TYPE
            WAFER_57PT      (2) Currently only 0, 1, 4, 5 and 8 active
            WAFER_121PT     (3)
            PLATE_9PT       (4) Square plate pattern grid
            PLATE_25PT      (5)
            PLATE_36PT      (6)
            PLATE_49PT      (7)
            LITHO_9PT       (8) Lithographically patterned spots
        """
        pts = [9, 25, 57, 121, 9, 25, 36, 49, 9]
        return pts

    def POSN1D_structure_format(self):
        """
        Returns structure format of the POSN, but only the z component
        Used to send and/or receive z format doubles
        """
        s_struct  = "<"
        s_struct += "d "   #z
        return s_struct, struct.Struct(s_struct)

    def POSN3D_structure_format(self):
        """
        Returns structure format of the POSN.
        Used to send and/or receive x y z format doubles
        """
        s_struct  = "<"
        s_struct += "d "   #x
        s_struct += "d "   #y
        s_struct += "d "   #z
        return s_struct, struct.Struct(s_struct)

    def CALIB_PT_structure_format(self):
        """
        Returns structure format of CALIB_PT
        Used to send and/or receive info about calibration on the grid
        """
        s_struct  = "<"
        s_struct += "d "   #x
        s_struct += "d "   #y
        s_struct += "d "   #z
        s_struct += "I "   #true/false if calibrated
        #s_struct += "q "   #true/false if calibrated
        return s_struct, struct.Struct(s_struct)

    def CALIB_PT_structure_format_out(self):
        """
        Returns structure format of CALIB_PT
        Used to send and/or receive info about calibration on the grid
        """
        s_struct  = "<"
        s_struct += "d "   #x
        s_struct += "d "   #y
        s_struct += "d "   #z
        s_struct += "I "   #true/false if calibrated
        #s_struct += "q "   #true/false if calibrated
        return s_struct, struct.Struct(s_struct)

    def set_SERVER_END(self, msg_id):
        """
        Shuts down the LasGo server.
        """
        msg = [0, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        return msg_recv[3]

    def get_FOCUS_QUERY_VERSION(self, msg_id):
        """
        Returns version of the focus server.
        """
        msg = [1, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0)
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Server version %d", msg_recv[3])
        return msg_recv[3]

    def get_FOCUS_QUERY_SAMPLE_ID(self, msg_id):
        """
        Returns sample ID as a string
        """
        msg = [2, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        #Receive the ID string
        data_size = msg_recv[4] 
        s_struct, unpacker = self.string_packer_format(data_size)
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_string = data_recv[0].decode('utf-8', errors = "ignore").split('\x00', 1)[0]
        return data_string

    def set_FOCUS_SET_SAMPLE_ID(self, msg_id, message_str):
        """
        Sets the current sample ID
        """
        msg = [3, msg_id, 0, 0, 0]
        # Prepare data
        message_str_c = message_str.encode('utf-8')
        data = [message_str_c]
        s_struct, packer = self.string_packer_format(len(data[0]))
        packed_data, values = self.pack_data(packer, data)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set sample ID, %d", msg_recv[3])
            return
        return int(msg_recv[3])

    def get_FOCUS_QUERY_SAMPLE_TEXT(self, msg_id):
        """
        Returns sample description as a string
        """
        msg = [4, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        #Receive the ID string
        data_size = msg_recv[4] 
        s_struct, unpacker = self.string_packer_format(data_size)
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_recv = data_recv[0].decode('utf-8', errors = "ignore").split('\x00', 1)[0]
        return data_recv

    def set_FOCUS_SET_SAMPLE_TEXT(self, msg_id, message_str):
        """
        Set the current sample description
        """
        msg = [5, msg_id, 0, 0, 0]
        # Prepare data
        message_str_c = message_str.encode('utf-8')
        data = [message_str_c]
        s_struct, packer = self.string_packer_format(len(data[0]))
        packed_data, values = self.pack_data(packer, data)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set sample ID, %d", msg_recv[3])
            return
        return msg_recv[3]

    def get_FOCUS_QUERY_POSN(self, msg_id):
        """
        Get the current position 
        """
        msg = [6, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        # Receive the structure data
        s_struct, unpacker = self.POSN3D_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        return data_recv

    def get_FOCUS_QUERY_FOCUS(self, msg_id, pos):
        """
        Get the focus value given at a positon pos = [x, y]
        """
        if len(pos) != 2:
            self.logger.error("There must be exaclty 2 real values provided to get position")
            return
        ppos = cp.deepcopy(pos)
        ppos.append(0.) #Fill the position with a dummy value to make it POSN3D compatible
        msg = [7, msg_id, 0, 0, 0]
        # Prepare settings data
        s_struct, packer = self.POSN3D_structure_format()
        packed_data, values = self.pack_data(packer, ppos)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to get the get the focus, %d", msg_recv[3])
            return msg_recv[3]
        #Receive the structure data
        s_struct, unpacker = self.POSN3D_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        #Focus is the last element only
        return data_recv[-1]

    def set_FOCUS_GOTO_POSN(self, msg_id, pos):
        """
        Set the position 
        NOTE: 
            -999 for x, y, or z will leave this coordinate unchanged
            -998 for z will set focus based on the wafer calibration 
        """
        if len(pos) != 3:
            self.logger.error("There must be exaclty 3 real values provided to set position")
            return
        msg = [8, msg_id, 0, 0, 0]
        # Prepare settings data
        s_struct, packer = self.POSN3D_structure_format()
        packed_data, values = self.pack_data(packer, pos)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed goto position, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

    def get_FOCUS_QUERY_SPECIAL(self, msg_id, option):
        """
        Get special focus points
        option should be one of the following:
            BLANK      (0)     Index of the blank (off stage) position 
            MIRROR     (1)     Index of the mirror reference position 
            SILICON    (2)     Index of the silicon reference position 
            POSN_3     (3)     Index for third position 
            POSN_4     (4)     Index for fourth position 
        """
        msg = [9, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        # Receive the structure data
        s_struct, unpacker = self.POSN3D_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed get special position, %d", msg_recv[3])
            return
        return data_recv

    def set_FOCUS_SET_SPECIAL(self, msg_id, pos, option):
        """
        Set the position of the special points
        NOTE: 
            -999 for x, y, or z will leave this coordinate unchanged
            -998 for x will set focus based on the wafer calibration 
        option should be one of the following:
            BLANK      (0)     Index of the blank (off stage) position 
            MIRROR     (1)     Index of the mirror reference position 
            SILICON    (2)     Index of the silicon reference position 
            POSN_3     (3)     Index for third position 
            POSN_4     (4)     Index for fourth position 
        """
        if len(pos) != 3:
            self.logger.error("There must be exaclty 3 real values provided to set position")
            return
        msg = [10, msg_id, int(option), 0, 0]
        # Prepare settings data
        s_struct, packer = self.POSN3D_structure_format()
        packed_data, values = self.pack_data(packer, pos)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed set special point, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

    def set_FOCUS_GOTO_SPECIAL(self, msg_id, option):
        """
        Go to the position of special defined by option
        option should be one of the following:
            BLANK      (0)     Index of the blank (off stage) position 
            MIRROR     (1)     Index of the mirror reference position 
            SILICON    (2)     Index of the silicon reference position 
            POSN_3     (3)     Index for third position 
            POSN_4     (4)     Index for fourth position 
        """
        msg = [11, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to go to special point, %d", msg_recv[3])
            return
        return msg_recv[3]

    def get_FOCUS_QUERY_GRID_TYPE(self, msg_id):
        """
        Get the type of grid currently loaded in the focus
            WAFER_9PT   (0)     Circular wafer pattern grids
            WAFER_25PT  (1)     Make sure matches focus.h TESS_TYPE
            WAFER_57PT  (2)     Currently only 0, 1, 4, 5 and 8 active 
            WAFER_121PT (3)     
            PLATE_9PT   (4)     Square plate pattern grid 
            PLATE_25PT  (5)
            PLATE_36PT  (6)
            PLATE_49PT  (7)
            LITHO_9PT   (8)     Lithographically patterned spots
        Currently, 0, 1, 4, 5 and 8 are implemented
        """
        msg = [12, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if int(msg_recv[3]) == -1:
            self.logger.error("Failed to get grid type, %d", msg_recv[3])
            return
        return msg_recv[3]

    def set_FOCUS_SELECT_GRID_TYPE(self, msg_id, option):
        """
        Set the type of grid currently loaded in the focus
        """
        msg = [13, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set grid type, %d", msg_recv[3])
            return
        return msg_recv[3]

    def get_FOCUS_QUERY_SAMPLE_GRID(self, msg_id):
        """
        Get the focus on the grid, and the info it point is calibrated
        """
        msg = [14, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if int(msg_recv[3]) == -1:
            self.logger.error("Number of grid points is wrong, %d", msg_recv[3])
            return
        npts = int(msg_recv[3])
        s_struct, unpacker = self.CALIB_PT_structure_format()
        s_struct_all = "<"
        for i in range(npts):
            s_struct_all += s_struct[1:]
        unpacker_all = struct.Struct(s_struct_all)
        packed_data = self.sock.recv(unpacker_all.size)
        data_recv = self.unpack_data(unpacker_all, packed_data)
        if not self.check_msgid(msg_id, msg_recv): return
        #Convert to a list of dictionaries
        data_list = []
        for i in range(npts):
            index = i * 4
            data_dict = {}
            data_dict["pos"] = data_recv[index : index + 3]
            data_dict["calibrated"] = data_recv[index + 3]
            data_list.append(data_dict)
        return data_list

    def set_FOCUS_SET_SAMPLE_GRID(self, msg_id, grid_list):
        """
        Set the focus on the grid
        Grid is a list of dictionaries with "pos" and calibration
        """
        npts = len(grid_list)
        msg = [15, msg_id, npts, 0, 0]
        s_struct, unpacker = self.CALIB_PT_structure_format()
        s_struct_all = "<"
        data = []
        for d in grid_list:
            s_struct_all += s_struct[1:]
            data.extend(d["pos"])
            data.append(d["calibrated"])
        packer_all = struct.Struct(s_struct_all)
        packed_data, values = self.pack_data(packer_all, data)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc) 
        msg[4] = packer_all.size
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set focus on grid, %d", msg_recv[3])
            return
        return

    def set_FOCUS_GOTO_SAMPLE_GRID(self, msg_id, option):
        """
        Goto the position of index option in the current grid
        """
        msg = [16, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to goto grid point, %d, %d", msg_recv[3], option)
            return
        return msg_recv[3]

    def get_FOCUS_QUERY_Z_MOTOR_STATUS(self, msg_id):
        """
        /* definitions of bits returned from the FM_MOTOR structure (FM_ACTION) */
        #define	FM_MOTOR_STATUS_ACTIVE		(0x0001)		/* motor is active */
        #define	FM_MOTOR_STATUS_ENGAGED		(0x0002)		/* motor is engaged */
        #define	FM_MOTOR_STATUS_HOMING		(0x0004)		/* motor is currently homing */
        #define	FM_MOTOR_STATUS_HOMED		(0x0008)		/* motor has been homed */
        #define	FM_MOTOR_STATUS_MOVING		(0x0010)		/* motor is currently moving */
        #define	FM_MOTOR_STATUS_SWEEP		(0x0100)		/* motor is sweeping through focus */
        #define	FM_MOTOR_STATUS_INVALID		(0xF000)		/* status word is invalid (error) */
        """
        msg = [17, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Failed to aquire z motor status, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

#    def get_FOCUS_QUERY_Z_MOTOR(self, msg_id):
    def get_FOCUS_QUERY_Z_MOTOR_ENGAGE(self, msg_id):
        """
        Returns if the z-motor is currently engaged (1), or it is free (0)
        """
        msg = [18, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Failed to aquire z motor status, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

#    def set_FOCUS_SET_Z_MOTOR(self, msg_id, option):
    def set_FOCUS_SET_Z_MOTOR_ENGAGE(self, msg_id, option):
        """
        Sets the z-motor status to engaged (1), or free (0)
        """
        msg = [19, msg_id, int(option), 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to set z motor status, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

    def get_FOCUS_QUERY_Z_MOTOR_POSN(self, msg_id):
        """
        Gets the current z value of the focus motor
        """
        msg = [20, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) == -1:
            self.logger.error("Failed to aquire z motor pos, %d", msg_recv[3])
            return msg_recv[3]
        # Receive the structure data
        s_struct, unpacker = self.POSN1D_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        return data_recv

    def set_FOCUS_SET_Z_MOTOR_POSN(self, msg_id, z):
        """
        Set the position of the z motor
        """
        msg = [21, msg_id, 0, 0, 0]
        # Prepare settings data
        s_struct, packer = self.POSN1D_structure_format()
        packed_data, values = self.pack_data(packer, z)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed goto position, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

    def set_FOCUS_SET_Z_MOTOR_POSN_WAIT(self, msg_id, z):
        """
        Set the position of the z motor, return when done
        """
        msg = [22, msg_id, 0, 0, 0]
        # Prepare settings data
        s_struct, packer = self.POSN1D_structure_format()
        packed_data, values = self.pack_data(packer, z)
        msg[4] = packer.size
        if self.crc:
            crc = self.get_crc(packed_data)
            msg.append(crc)
        self.comm_send_struct(msg)
        # Send data
        self.sock.sendall(packed_data)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed goto position, %d", msg_recv[3])
            return msg_recv[3]
        return msg_recv[3]

def test_all_functions():
    with open('logging.yaml', 'r') as f:
        log_cfg = yaml.safe_load(f.read())
    logging.config.dictConfig(log_cfg)
    msg_id = 101
    #address = "LSA"
    #address = "Analysis"
    address = "Local"
    #address = "CHESS"
    camera_client = ClientDCXProtocol(connect = True, address = address)
    lasgo_client = ClientLasGoProtocol_Struct(connect = True, address = address)
    #spec_client = ClientSpecProtocol(connect = True, address = address)
    #focus_client = ClientFocusProtocol(connect = True, address = address)
    lsa = ds.LSA()
    conditions = lsa.read("generated_lsa_gd.csv")
    try:
        recv = camera_client.get_DCX_RING_IMAGE_N_DATA(msg_id, 0)
        recv = camera_client.get_DCX_GET_EXPOSURE_PARMS(msg_id)
        exposure_dict = {}
        exposure_dict["EXPOSURE"]    = 0.01
        exposure_dict["FPS"]         = 8
        exposure_dict["GAMMA"]       = 20
        exposure_dict["MASTER_GAIN"] = 40
        exposure_dict["RED_GAIN"]    = 30
        exposure_dict["GREEN_GAIN"]  = 20
        exposure_dict["BLUE_GAIN"]   = 10
        params_to_set = {}
        params_to_set["EXPOSURE"]    =  False
        params_to_set["FPS"]         =  False
        params_to_set["GAMMA"]       =  True
        params_to_set["MASTER_GAIN"] =  False
        params_to_set["RED_GAIN"]    =  True
        params_to_set["GREEN_GAIN"]  =  False
        params_to_set["BLUE_GAIN"]   =  False
        recv = camera_client.set_DCX_SET_EXPOSURE_PARMS(msg_id, exposure_dict, params_to_set)
        recv = camera_client.get_DCX_QUERY_VERSION(msg_id)
        camera_info = camera_client.get_DCX_GET_CAMERA_INFO(msg_id)
        recv = camera_client.get_DCX_ACQUIRE_IMAGE(msg_id)
        image_info = camera_client.get_DCX_GET_IMAGE_INFO(msg_id)
        #camera_client.set_DCX_SET_EXPOSURE(msg_id, 120.0)
        #camera_client.set_DCX_SET_GAINS(msg_id, [80, 20, 20, 20])
        img, img_info= camera_client.get_image(msg_id)
        if camera_info["color_mode"] == 1:
            #Greyscale image
            plt.imshow(img,aspect='auto', cmap='gray', vmin=0, vmax=255)
        elif camera_info["color_mode"] == 0:
            #RGB image
            plt.imshow(img,aspect='auto')
        #plt.show()
        recv = camera_client.get_DCX_GET_EXPOSURE_PARMS(msg_id)
        recv = camera_client.set_DCX_SET_EXPOSURE_PARMS(msg_id, recv)
        recv = camera_client.get_DCX_RING_INFO(msg_id)
        recv = camera_client.get_DCX_RING_GET_SIZE(msg_id)
        recv = camera_client.set_DCX_RING_SET_SIZE(msg_id, 5)
        recv = camera_client.set_DCX_VIDEO_ENABLE(msg_id, 0)
        recv = camera_client.set_DCX_BURST_ARM(msg_id)

        #Run lasgo
        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
        option = lasgo_client.option_LASGO_EXECUTE_ZONE_SCAN(1, 0)
        print(recv)
        #recv["Scan"] = 0
        recv["Power"] = 20.
        recv["Dwell"] = 20000.
        recv["Ymin"] = -15.
        recv["Ymax"] = 15.
        recv["Xmin"] = 0.
        recv["Xmax"] = 0.
        recs = [recv]
        rec = lasgo_client.set_LASGO_VALIDATE_ZONE_SCAN(msg_id, option, recs[0])#Should rewrite handling zones (plural)
        if rec !=0:
            print("Lasgo returns that the requested zone cannot be executed. Returning with the return code")
            print("Error code", rec)
        print(rec)
        recv = lasgo_client.set_LASGO_EXECUTE_ZONE_SCAN(msg_id, option, recs, timeout = 100000)
        recv = lasgo_client.get_LASGO_QUERY_STATUS(msg_id)
        #Run lasgo


        recv = camera_client.get_DCX_RING_GET_FRAME_CNT(msg_id)
        recv = camera_client.get_DCX_RING_IMAGE_N_DATA(msg_id, 0)
        recv = camera_client.set_DCX_BURST_ABORT(msg_id)
        recv = camera_client.get_DCX_BURST_STATUS(msg_id)
        recv = camera_client.set_DCX_BURST_WAIT(msg_id, 5000)
        recv = camera_client.set_DCX_LED_SET_STATE(msg_id, 1)
        recv = camera_client.set_DCX_VIDEO_ENABLE(msg_id, 1)
        recv = camera_client.set_DCX_SAVE_IMAGE_BUFFERS(msg_id)
        #Camera part ends here
        return

        recv = focus_client.get_FOCUS_QUERY_VERSION(msg_id)
        recv = focus_client.get_FOCUS_QUERY_SAMPLE_ID(msg_id)
        recv = focus_client.set_FOCUS_SET_SAMPLE_ID(msg_id, "MySample")
        recv = focus_client.get_FOCUS_QUERY_SAMPLE_TEXT(msg_id)
        recv = focus_client.set_FOCUS_SET_SAMPLE_TEXT(msg_id, "MySampleText")
        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
        recv = focus_client.get_FOCUS_QUERY_FOCUS(msg_id, [0., 1.])
        recv = focus_client.set_FOCUS_GOTO_POSN(msg_id, [2., 5., -999])
        recv = focus_client.get_FOCUS_QUERY_SPECIAL(msg_id, 0)
        recv = focus_client.set_FOCUS_SET_SPECIAL(msg_id, recv, 0)
        recv = focus_client.set_FOCUS_GOTO_SPECIAL(msg_id, 0)
        recv = focus_client.set_FOCUS_GOTO_SPECIAL(msg_id, 1)
        recv = focus_client.get_FOCUS_QUERY_GRID_TYPE(msg_id)
        recv = focus_client.set_FOCUS_SELECT_GRID_TYPE(msg_id, 1)
        recv = focus_client.get_FOCUS_QUERY_SAMPLE_GRID(msg_id)
        grid = cp.deepcopy(recv)
        for i in grid:
            i["pos"][2] = 1.22
        recv = focus_client.set_FOCUS_SET_SAMPLE_GRID(msg_id, grid)
        recv = focus_client.set_FOCUS_GOTO_SAMPLE_GRID(msg_id, 20)
        recv = focus_client.get_FOCUS_QUERY_Z_MOTOR_STATUS(msg_id)
        recv = focus_client.get_FOCUS_QUERY_Z_MOTOR_ENGAGE(msg_id)
        recv = focus_client.set_FOCUS_SET_Z_MOTOR_ENGAGE(msg_id, 1)
        recv = focus_client.get_FOCUS_QUERY_Z_MOTOR_POSN(msg_id)
        print("POSN is", recv)
        recv = focus_client.set_FOCUS_SET_Z_MOTOR_POSN(msg_id, 2.)
        recv = focus_client.set_FOCUS_SET_Z_MOTOR_POSN_WAIT(msg_id, 3.)
        recv = focus_client.get_FOCUS_QUERY_Z_MOTOR_POSN(msg_id)
        print("POSN is", recv)
#Extract grids implemented in focus
        gridpoints = [9, 25, 57, 121, 9, 25, 36, 49, 9]
        gridtypes = [0, 1, 4, 5, 8] 
        gridnames = ["WAFER_9PT", "WAFER_25PT", "PLATE_9PT",  "PLATE_25PT" ,"LITHO_9PT"]  
        grid = []
        for t in gridtypes:
            recv = focus_client.set_FOCUS_SELECT_GRID_TYPE(msg_id, t)
            recv = focus_client.get_FOCUS_QUERY_SAMPLE_GRID(msg_id)
            g = [i['pos'] for i in recv]
            grid.append(g)
        for i, n, g in zip(gridtypes, gridnames, grid):
            print("Name", n, "number of grid points", gridpoints[i], "index", i)
            for ig in g:
                print('{:16.8f} {:16.8f}'.format(ig[0], ig[1]))

        recv = lasgo_client.get_LASGO_QUERY_VERSION(msg_id)
        recv = lasgo_client.get_LASGO_GET_TRANSFORM(msg_id)
        recv = lasgo_client.set_LASGO_SET_ORIGIN(msg_id, "Spectrometer")
        recv = lasgo_client.get_LASGO_GET_POSN(msg_id, 0)
        recv = lasgo_client.set_LASGO_MOVE_TO(msg_id, 1, [2. ,5. ])
        recv = lasgo_client.set_LASGO_QUEUE_TO(msg_id, 1, [2. ,5. ])
        recv = lasgo_client.get_LASGO_WAIT_MOVE_DONE(msg_id)
        recv = lasgo_client.get_LASGO_QUERY_RAW_STATUS(msg_id)
        recv = lasgo_client.set_LASGO_ABORT_MOVE(msg_id, 1.)
        recv = lasgo_client.set_LASGO_PANIC(msg_id, 1.)
        data_dict = lasgo_client.dict_LASGO_EXECUTE_FLYSCAN()
        data_dict["cordsys"]            = 0        #int:   0 and 1 for user or world coordinates
        data_dict["pos_start"]          = [2., 3.] #float: list of 2, x and y
        data_dict["pos_end"]            = [2., 3.] #float: list of 2, x and y
        data_dict["vel"]                = 1.       #float: scan velocity
        data_dict["msRampTime"]         = 1.       #float: ms for ramping to vel 
        data_dict["gMaxAccel"]          = 1.       #float: maximum g's of accelerateion 
        data_dict["mmConstVel"]         = 1.       #float: mm of constant velocity before shutter 
        data_dict["mmTriggerSpacing"]   = 1.       #float: spacing between collection triggers 
        recv = lasgo_client.set_LASGO_EXECUTE_FLYSCAN(msg_id, data_dict)
        recv = lasgo_client.get_LASGO_QUERY_FLYSCAN_TRIG(msg_id)
        recv = lasgo_client.get_LASGO_GET_JOB_STRUCT(msg_id, 0)
        recv = lasgo_client.set_LASGO_SET_JOB_STRUCT(msg_id, recv)
        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
        recv = lasgo_client.set_LASGO_VALIDATE_ZONE_SCAN(msg_id, 100, recv)
        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
        option = lasgo_client.option_LASGO_EXECUTE_ZONE_SCAN(5, 0)
        recs = [recv, recv, recv, recv, recv]
        recv = lasgo_client.set_LASGO_EXECUTE_ZONE_SCAN(msg_id, option, recs, timeout = 100000)
        recv = lasgo_client.get_LASGO_QUERY_STATUS(msg_id)

        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
        recv = spec_client.get_SPEC_GET_SPECTROMETER_INFO(msg_id)
        recv = spec_client.get_SPEC_GET_WAVELENGTHS(msg_id, recv)
        recv = spec_client.get_SPEC_GET_INTEGRATION_PARMS(msg_id)
        recv = spec_client.set_SPEC_SET_INTEGRATION_PARMS(msg_id, recv)
        recv = spec_client.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
        recv = spec_client.get_SPEC_GET_SPECTRUM_INFO(msg_id)
        recv = spec_client.get_SPEC_GET_SPECTRUM_DATA(msg_id, recv)

        ##for c in conditions:
        ##    recv = focus_client.set_FOCUS_GOTO_POSN(msg_id, [c["x"], c["y"], -999])
        ##    img, img_info= camera_client.get_image(msg_id)
        ##    if camera_info["color_mode"] == 1:
        ##        #Greyscale image
        ##        plt.imshow(img,aspect='auto', cmap='gray', vmin=0, vmax=255)
        ##    elif camera_info["color_mode"] == 0:
        ##        #RGB image
        ##        plt.imshow(img,aspect='auto')
        ##    plt.show()
        ##    recv = spec_client.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
        ##    recv = spec_client.get_SPEC_GET_SPECTRUM_INFO(msg_id)
        ##    recv = spec_client.get_SPEC_GET_SPECTRUM_DATA(msg_id, recv)

    finally:
        print ('Closing socket')
        focus_client.close_socket()
        lasgo_client.close_socket()
        spec_client.close_socket()
        camera_client.close_socket()
    
if __name__ == "__main__":

    test_all_functions()

####    with open('logging.yaml', 'r') as f:
####        log_cfg = yaml.safe_load(f.read())
####    logging.config.dictConfig(log_cfg)
####    msg_id = 101
####    address = "128.253.129.71"
####    port = 996
####    lasgo_client = ClientLasGoProtocol_Struct(connect = False)
####    lasgo_client.open_socket(address, port)
##########    port = 994
##########    lasgo_client_txt = ClientLasGoProtocol()
##########    port = 985
##########    spec_client = ClientSpecProtocol(connect = True, address =  "Analysis", port = "spec")
##########    port = 985
##########    camera_client = ClientDCXProtocol()
####    port = 980
####    focus_client = ClientFocusProtocol()
######
######
######    address = "Local"
######    camera_client = ClientDCXProtocol(connect = True, address = address)
######    lasgo_client = ClientLasGoProtocol_Struct(connect = True, address = address)
######    spec_client = ClientSpecProtocol(connect = True, address = address)
######    focus_client = ClientFocusProtocol(connect = True, address = address)
######
####    try:
######        camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
######        camera_info = camera_client.get_DCX_GET_CAMERA_INFO(msg_id)
######        camera_client.get_DCX_ACQUIRE_IMAGE(msg_id)
######        image_info = camera_client.get_DCX_GET_IMAGE_INFO(msg_id)
######        camera_client.get_DCX_GET_CURRENT_IMAGE(msg_id, image_info)
######        camera_client.set_DCX_SET_EXPOSURE(msg_id,120.0)
######        camera_client.set_DCX_SET_GAINS(msg_id, [80, 20, 20, 20])
######        img, img_info= camera_client.get_image(msg_id)
#######        if camera_info["color_mode"] == 1:
#######            #Greyscale image
#######            plt.imshow(img,aspect='auto', cmap='gray', vmin=0, vmax=255)
#######        elif camera_info["color_mode"] == 0:
#######            #RGB image
#######            plt.imshow(img,aspect='auto')
#######        plt.show()
######
######        recv = focus_client.get_FOCUS_QUERY_VERSION(msg_id)
######        recv = focus_client.get_FOCUS_QUERY_SAMPLE_ID(msg_id)
######        recv = focus_client.set_FOCUS_SET_SAMPLE_ID(msg_id, "MySample")
######        recv = focus_client.get_FOCUS_QUERY_SAMPLE_TEXT(msg_id)
######        recv = focus_client.set_FOCUS_SET_SAMPLE_TEXT(msg_id, "MySampleText")
######        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
######        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
######        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
######        recv = focus_client.get_FOCUS_QUERY_POSN(msg_id)
######        recv = focus_client.get_FOCUS_QUERY_FOCUS(msg_id, [0., 1.])
######        recv = focus_client.set_FOCUS_GOTO_POSN(msg_id, [1., 1., -999])
######        recv = focus_client.get_FOCUS_QUERY_SPECIAL(msg_id, 3)
######        recv = focus_client.set_FOCUS_SET_SPECIAL(msg_id, [1., 1., 1.], 0)
######        recv = focus_client.set_FOCUS_GOTO_SPECIAL(msg_id, 0)
######        recv = focus_client.get_FOCUS_QUERY_GRID_TYPE(msg_id)
######        recv = focus_client.set_FOCUS_SELECT_GRID_TYPE(msg_id, 1)
####        recv = focus_client.get_FOCUS_QUERY_SAMPLE_GRID(msg_id)
####        print(recv)
######        grid = cp.deepcopy(recv)
######        for i in grid:
######            i["pos"][2] = 1.22
######        recv = focus_client.set_FOCUS_SET_SAMPLE_GRID(msg_id, grid)
######        recv = focus_client.set_FOCUS_GOTO_SAMPLE_GRID(msg_id, 20)
######        recv = focus_client.get_FOCUS_QUERY_Z_MOTOR(msg_id)
######        recv = focus_client.set_FOCUS_SET_Z_MOTOR(msg_id, 0)
######
######        recv = lasgo_client.get_LASGO_QUERY_VERSION(msg_id)
####        recv = lasgo_client.get_LASGO_GET_TRANSFORM(msg_id)
####        print(recv)
######        recv = lasgo_client.set_LASGO_SET_ORIGIN(msg_id, "Spectrometer")
######        recv = lasgo_client.get_LASGO_GET_POSN(msg_id, 0)
######        recv = lasgo_client.set_LASGO_MOVE_TO(msg_id, 1, [1. ,1. ])
######        recv = lasgo_client.set_LASGO_QUEUE_TO(msg_id, 1, [1. ,1. ])
######        recv = lasgo_client.get_LASGO_WAIT_MOVE_DONE(msg_id)
####        recv = lasgo_client.get_LASGO_QUERY_RAW_STATUS(msg_id)
####        print(recv)
######        recv = lasgo_client.set_LASGO_ABORT_MOVE(msg_id, 1.)
######        recv = lasgo_client.set_LASGO_PANIC(msg_id, 1.)
######        data_dict = lasgo_client.dict_LASGO_EXECUTE_FLYSCAN()
######        data_dict["cordsys"]            = 0        #int:   0 and 1 for user or world coordinates
######        data_dict["pos_start"]          = [2., 3.] #float: list of 2, x and y
######        data_dict["pos_end"]            = [2., 3.] #float: list of 2, x and y
######        data_dict["vel"]                = 1.       #float: scan velocity
######        data_dict["msRampTime"]         = 1.       #float: ms for ramping to vel 
######        data_dict["gMaxAccel"]          = 1.       #float: maximum g's of accelerateion 
######        data_dict["mmConstVel"]         = 1.       #float: mm of constant velocity before shutter 
######        data_dict["mmTriggerSpacing"]   = 1.       #float: spacing between collection triggers 
######        recv = lasgo_client.set_LASGO_EXECUTE_FLYSCAN(msg_id, data_dict)
######        recv = lasgo_client.get_LASGO_QUERY_FLYSCAN_TRIG(msg_id)
####        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
####        print(recv)
######        recv = lasgo_client.set_LASGO_SET_JOB_STRUCT(msg_id, recv)
######        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
######        recv = lasgo_client.set_LASGO_VALIDATE_ZONE_SCAN(msg_id, 100, recv)
######        recv = lasgo_client.get_LASGO_GET_ZONE_STRUCT(msg_id)
######        option = lasgo_client.option_LASGO_EXECUTE_ZONE_SCAN(5, 0)
######        recs = [recv, recv, recv, recv, recv]
######        recv = lasgo_client.set_LASGO_EXECUTE_ZONE_SCAN(msg_id, option, recs, timeout = 100000)
######        recv = lasgo_client.get_LASGO_QUERY_STATUS(msg_id)
######
######        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
######        recv = spec_client.get_SPEC_GET_SPECTROMETER_INFO(msg_id)
######        recv = spec_client.get_SPEC_GET_WAVELENGTHS(msg_id, recv)
######        recv = spec_client.get_SPEC_GET_INTEGRATION_PARMS(msg_id)
######        recv = spec_client.set_SPEC_SET_INTEGRATION_PARMS(msg_id, recv)
######        recv = spec_client.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
######        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
######        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
######        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
######        recv = spec_client.get_SPEC_QUERY_VERSION(msg_id)
######        recv = spec_client.get_SPEC_GET_SPECTRUM_INFO(msg_id)
######        recv = spec_client.get_SPEC_GET_SPECTRUM_DATA(msg_id, recv)
######        #wl   = spec_client.get_wavelengths(12)
######        #spec = spec_client.get_spectrum(12)
######        ###pos = [0., 0.]
######        ###length = 40.
######        ###power =  75.
######        ###dwell  = 1000.
######        ###zone = lasgo_client.execute_LSA_zone_at(msg_id, pos, length, power, dwell, id = "Max-Zone")
######        ##print(rec)
#######    finally:
#######        lasgo_client.close_socket()
#######
#######    
##########    camera_client = ClientDCXProtocol()
#################    #address = "128.253.129.71"
#################    #port = 985
##########    address = address = socket.gethostname()
##########    port = 1985
##########    camera_client.open_socket(address,port)
##########    msg_id = 101
######################    try:
######################        camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
######################        camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
######################        camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
######################        camera_info = camera_client.get_DCX_GET_CAMERA_INFO(msg_id)
######################        camera_client.get_DCX_ACQUIRE_IMAGE(msg_id)
######################        image_info = camera_client.get_DCX_GET_IMAGE_INFO(msg_id)
######################        camera_client.get_DCX_GET_CURRENT_IMAGE(msg_id, image_info)
######################        camera_client.set_DCX_SET_EXPOSURE(msg_id,120.0)
######################        camera_client.set_DCX_SET_GAINS(msg_id,[80,20,20,20])
#######################        img, img_info= camera_client.get_image(msg_id)
######################        ##if camera_info["color_mode"] == 1:
######################        ##    #Greyscale image
######################        ##    plt.imshow(img,aspect='auto', cmap='gray', vmin=0, vmax=255)
######################        ##elif camera_info["color_mode"] == 0:
######################        ##    #RGB image
######################        ##    plt.imshow(img,aspect='auto')
######################        ##plt.show()
#################    finally:
#################        print ('Closing socket')
#################        camera_client.close_socket()
#################    
#########    spec_client = ClientSpecProtocol()
#########    address = "128.253.129.71"
#########    port = 983
##########    address = address = socket.gethostname()
##########    port = 1983
#########    spec_client.open_socket(address,port)
#########    msg_id = 101
#########    try:
#########        print(spec_client.get_SPEC_QUERY_VERSION(msg_id))
#########        dev_info = spec_client.get_SPEC_GET_SPECTROMETER_INFO(msg_id)
#########        wl = spec_client.get_SPEC_GET_WAVELENGTHS(msg_id,dev_info)
#########        spec_client.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
#########        spec_info = spec_client.get_SPEC_GET_SPECTRUM_INFO(msg_id)
#########        print(spec_info)
#########        spec = spec_client.get_SPEC_GET_SPECTRUM_DATA(msg_id, dev_info)
#########        #wl   = spec_client.get_wavelengths(12)
#########        #spec = spec_client.get_spectrum(12)
#########        
#########    finally:
#########        print ('Closing socket')
#########        spec_client.close_socket()
###########    
###########    lasgo_client = ClientLasGoProtocol()
###########    address = "128.253.129.71"
###########    port = 994
##########
##########    logger = logging.info("Hello")
##########    lasgo_client = ClientLasGoProtocol()
##########    address = socket.gethostname()
##########    port = 1994
##########    lasgo_client.open_socket(address,port)
##############    msg_id = 101
##############    try:
##############        lasgo_client.set_device(10)
##############        lasgo_client.wait()
##############        lasgo_client.get_version()
##############        lasgo_client.moveto(0.,0.)
##############        lasgo_client.moveto_queue(0.,0.)
##############        lasgo_client.get_position()
##############        lasgo_client.get_device()
##############        lasgo_client.abort()
##############        lasgo_client.panic()
##############        lasgo_client.status()
##############        lasgo_client.get_version()
##########
##########    #    lasgo_client.moveto_safe([20.,20.])
##########    #    print("Device",lasgo_client.get_device())
##########    #    positions = [[40.,30.,],[30.,15.,],[10.,22.],[-10.,-4.],[40.,30.,],[30.,15.,],[10.,22.],[-10.,-4.]]
##########    #    for i in positions:
##########    #        lasgo_client.moveto_safe(i)
##########    #finally:
##########    #    lasgo_client.close_socket()
##########    focus_client = ClientFocusProtocol()
###########    address = "128.253.129.71"
###########    port = 983
##########    address = address = socket.gethostname()
##########    port = 1980
##########    focus_client.open_socket(address,port)
##########    msg_id = 101
##########    try:
##########        for i in range (1000):
##########            print(focus_client.get_FOCUS_QUERY_VERSION(msg_id))
##########            print(focus_client.get_FOCUS_QUERY_SAMPLE_ID(msg_id))
##########            print(focus_client.get_FOCUS_QUERY_SAMPLE_ID(msg_id))
##########            print(focus_client.get_FOCUS_QUERY_SAMPLE_ID(msg_id))
##########            print(focus_client.set_FOCUS_SET_SAMPLE_ID(msg_id, "Best Sample"))
##########            print(focus_client.get_FOCUS_QUERY_SAMPLE_DESCRIPTION(msg_id))
##########            print(focus_client.set_FOCUS_SET_SAMPLE_DESCRIPTION(msg_id, "Best Composition"))
##########            print(focus_client.get_FOCUS_QUERY_POSITION(msg_id))
##########            print(focus_client.set_FOCUS_GOTO_POSITION(msg_id, [2., 3., 4.]))
##########
##########            camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
##########            camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
##########            camera_version = camera_client.get_DCX_QUERY_VERSION(msg_id)
##########            camera_info = camera_client.get_DCX_GET_CAMERA_INFO(msg_id)
##########            camera_client.get_DCX_ACQUIRE_IMAGE(msg_id)
##########            image_info = camera_client.get_DCX_GET_IMAGE_INFO(msg_id)
##########            camera_client.get_DCX_GET_CURRENT_IMAGE(msg_id, image_info)
##########            camera_client.set_DCX_SET_EXPOSURE(msg_id,120.0)
##########            camera_client.set_DCX_SET_GAINS(msg_id,[80,20,20,20])
##########
##########            lasgo_client.set_device(10)
##########            lasgo_client.wait()
##########            lasgo_client.get_version()
##########            lasgo_client.moveto(0.,0.)
##########            lasgo_client.moveto_queue(0.,0.)
##########            lasgo_client.get_position()
##########            lasgo_client.get_device()
##########            lasgo_client.abort()
##########            lasgo_client.panic()
##########            lasgo_client.status()
##########            lasgo_client.get_version()
##########            
##########            print(spec_client.get_SPEC_QUERY_VERSION(msg_id))
##########            dev_info = spec_client.get_SPEC_GET_SPECTROMETER_INFO(msg_id)
##########            wl = spec_client.get_SPEC_GET_WAVELENGTHS(msg_id,dev_info)
##########            spec_client.get_SPEC_ACQUIRE_SPECTRUM(msg_id)
##########            spec_info = spec_client.get_SPEC_GET_SPECTRUM_INFO(msg_id)
##########            spec = spec_client.get_SPEC_GET_SPECTRUM_DATA(msg_id, dev_info)
##########            #wl   = spec_client.get_wavelengths(12)
##########            #spec = spec_client.get_spectrum(12)
####    finally:
####        print ('Closing socket')
#####        focus_client.close_socket()
####        lasgo_client.close_socket()
#####        spec_client.close_socket()
#####        camera_client.close_socket()
####    
