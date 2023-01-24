from sara_client import ClientStructProtocol
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
import cv2
with open('logging.yaml', 'r') as f:
    log_cfg = yaml.safe_load(f.read())
logging.config.dictConfig(log_cfg)

class ClientZOOCAMProtocol(ClientStructProtocol):
    """
    Subclass with functions implemented specifically for the ZOOCAM camera.
    Relies on the ClientStructProtocol class.
    """
    def __init__(self, connect = True, address = None, port = None):
        super(ClientZOOCAMProtocol, self).__init__()
        self.logger = logging.getLogger("ClientZOOCAM")
        self.rotate = None
        if address is None:
            address = self.addresses["Analysis"] 
        if port is None:
            port = "camera" 
        self.success = self.autoconnect(connect, address, port)
        if self.success != 0:
            self.logger.error('Autoconnect failed')
            #return -1

    def get_ZOOCAM_QUERY_VERSION(self, msg_id):
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

    #Block dealing with ZOOCAM_GET_CAMERA_INFO*****************************************
    def ZOOCAM_GET_CAMERA_INFO_structure_format(self):
        """
        Returns structure format of the camera info.
        """
        s_struct  = "<"
        s_struct += "I "   #Camera type: CAMERA_UNKNOWN=0, CAMERA_DCX=1, CAMERA_TL=2
        s_struct += "32s " #Camera name
        s_struct += "32s " #Camera model
        s_struct += "32s " #Camera sensor manufacturer
        s_struct += "32s " #Camera serial number
        s_struct += "32s " #Camera version
        s_struct += "32s " #Firmware date
        s_struct += "I "   #width
        s_struct += "I "   #height
        s_struct += "I "   #Is camera color (bool)??
        s_struct += "d "   #x_pixel_um;  /* Pixel size in um */
        s_struct += "d "   #y_pixel_um;  /* Pixel size in um */
        return s_struct, struct.Struct(s_struct)

    def ZOOCAM_GET_CAMERA_INFO_todict(self, data_list):
        """
        Transform list to dictionary of ZOOCAM_GET_CAMERA_INFO structure
        """
        data_dict = {}
        data_dict['type']              = data_list[0]  #Camera type
        data_dict['name']              = data_list[1].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera name
        data_dict['model']             = data_list[2].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera model 
        data_dict['manufacturer']      = data_list[3].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera manufacturer 
        data_dict['serial']            = data_list[4].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera serial number
        data_dict['version']           = data_list[5].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Camera version
        data_dict['date']              = data_list[6].decode('utf-8', errors = "ignore").split('\x00', 1)[0] #Firmware date
        data_dict['width']             = data_list[7]  #width
        data_dict['height']            = data_list[8]  #height
        data_dict['color_mode']        = data_list[9]  #Monochrome or color mode
        data_dict['pixel_width']       = data_list[10] #x_pixel_um Pixel size in um */
        data_dict['pixel_height']      = data_list[11] #y_pixel_um Pixel size in um */
        return data_dict

    def get_ZOOCAM_GET_CAMERA_INFO(self, msg_id, camera_id = None):
        """
        Wrapper function to get camera info.
        """
        msg = [2, msg_id, 0, 0, 0]
        if self.crc:
            msg.append(0) 
        if camera_id is None:
            msg[2] = 1
        else:
            msg[2] = camera_id
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        s_struct, unpacker = self.ZOOCAM_GET_CAMERA_INFO_structure_format()
        if int(msg_recv[3]) != 0:
            self.logger.error("Camera not connected")
            if msg_recv[4] == 0:
                return msg_recv[3]
            self.logger.error("Still receiving data")
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        data_recv_dict = self.ZOOCAM_GET_CAMERA_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with ZOOCAM_GET_CAMERA_INFO*****************************************

    #Block dealing with ZOOCAM_GET_EXPOSURE_PARMS********************************************
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
                #define ZOOCAMF_MODIFY_EXPOSURE     (0x01)   /* Modify exposure (value in ms) */
                #define ZOOCAMF_MODIFY_FPS          (0x02)   /* Modify frames per second */
                #define ZOOCAMF_MODIFY_GAMMA        (0x04)   /* Modify gamma */
                #define ZOOCAMF_MODIFY_MASTER_GAIN  (0x08)   /* Modify master gain */
                #define ZOOCAMF_MODIFY_RED_GAIN     (0x10)   /* Red channel gain */
                #define ZOOCAMF_MODIFY_GREEN_GAIN   (0x20)   /* Green channel gain */
                #define ZOOCAMF_MODIFY_BLUE_GAIN    (0x40)   /* Blue channel gain */
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
        /* Structure used by ZOOCAM_CLIENT to allow changes to exposure */
        """
        s_struct  = "<"
        s_struct += "d "  # double exposure;                         /* Exposure time in ms           
        s_struct += "d "  # double fps;                              /* Frame rate (per second)       
        s_struct += "d "  # double gamma;                          /* Gamma value (0 < gamma < 100) 
        s_struct += "d "  # double master_gain;                    /* Master gain (0 < gain < 100)  
        s_struct += "3d " # double red_gain, green_gain, blue_gain;/* Individual channel gains      
        return s_struct, struct.Struct(s_struct)

    def get_ZOOCAM_GET_EXPOSURE_PARMS(self, msg_id):
        """
        Wrapper function to get exposure params
        """
        msg = [3, msg_id, 0, 0, 0]
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
    #Block dealing with ZOOCAM_GET_EXPOSURE_PARMS********************************************

    #Block dealing with ZOOCAM_SET_EXPOSURE_PARMS********************************************
    def set_ZOOCAM_SET_EXPOSURE_PARMS(self, msg_id, exposure_dict, params_to_set = None):
        """
        Wrapper function to set exposure.
        """
        # Send comm data
        msg = [4, msg_id, 0, 0, 0] #Command index is 7, length of the subsequently sent data is 16, important
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
    #Block dealing with ZOOCAM_SET_EXPOSURE_PARMS********************************************

    def set_ZOOCAM_TRIGGER(self, msg_id): #Triggers the camera (action depends on trigger setting): Before ACQUIRE_IMAGE
        """
        Triggers the camera with given settigs
        """
        msg = [5, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        self.logger.debug("Trigger %d", msg_recv[3])
        if not self.check_msgid(msg_id, msg_recv): return
        return 

    #Block dealing with TRIGGER_INFO********************************************
    def ZOOCAM_TRIGGER_INFO_structure_format(self):
        """
        Returns structure format of the trigger info.
        mode (trigger mode)             : TRIG_FREERUN=0, TRIG_SOFTWARE=1, TRIG_EXTERNAL=2, TRIG_SS=3, TRIG_BURST=4
        ext_slope (trigger polarity)    : TRIG_EXT_NOCHANGE=0, TRIG_EXT_POS=1, TRIG_EXT_NEG=2, TRIG_EXT_UNSUPPORTED=3 
        capabilities:
            BOOL bFreerun:1;
            BOOL bSoftware:1;
            BOOL bExternal:1;
            BOOL bSingleShot:1;
            BOOL bBurst:1;
            BOOL bArmDisarm:1;
            BOOL bForceExtTrigger:1;
            BOOL bMultipleFramesPerTrigger:1; #These are single bits of a 32 bit string!!!
        """
        s_struct  = "<"
        s_struct += "I "   #mode            :Triggering mode
        s_struct += "I "   #ext_slope       :External trigger polarity
        s_struct += "I "   #capabilities    :Trigger capabilities, as 32 bit string
        s_struct += "I "   #Armed           :Bool
        s_struct += "I "   #frames          :Frames per trigger (in SOFTWARE / HARDWARE modes)
        s_struct += "I "   #msWait          :ms to wait for previous trig to complete before switch
        s_struct += "I "   #nBurst          :number of images to capture on software/external trigger
        return s_struct, struct.Struct(s_struct)

    def ZOOCAM_TRIGGER_INFO_SEND_structure_format(self):
        """
        Returns structure format of the trigger info.
        mode (trigger mode)             : TRIG_FREERUN=0, TRIG_SOFTWARE=1, TRIG_EXTERNAL=2, TRIG_SS=3, TRIG_BURST=4
        ext_slope (trigger polarity)    : TRIG_EXT_NOCHANGE=0, TRIG_EXT_POS=1, TRIG_EXT_NEG=2, TRIG_EXT_UNSUPPORTED=3 
        capabilities:
            BOOL bFreerun:1;
            BOOL bSoftware:1;
            BOOL bExternal:1;
            BOOL bSingleShot:1;
            BOOL bBurst:1;
            BOOL bArmDisarm:1;
            BOOL bForceExtTrigger:1;
            BOOL bMultipleFramesPerTrigger:1; #These are single bits of a 32 bit string!!!
        """
        s_struct  = "<"
        s_struct += "I "   #mode            :Triggering mode
        s_struct += "I "   #ext_slope       :External trigger polarity
        s_struct += "I "   #frames          :Frames per trigger (in SOFTWARE / HARDWARE modes)
        s_struct += "I "   #msWait          :ms to wait for previous trig to complete before switch
        s_struct += "I "   #nBurst          :number of images to capture on software/external trigger
        return s_struct, struct.Struct(s_struct)

    def ZOOCAM_TRIGGER_INFO_todict(self, data_list):
        """
        Transform list to dictionary of ZOOCAM_TRIGGER_INFO structure.
        """
        data_dict = {}
        data_dict['mode']                   =  data_list[0]  #Triggering mode
        data_dict['ext_slope']              =  data_list[1]  #External trigger polarity
        data_dict['capabilities']           =  data_list[2]  #Trigger capabilities, as 32 bit string
        data_dict['armed']                  =  data_list[3]  #Trigger capabilities, as 32 bit string
        data_dict['frames']                 =  data_list[4]  #Frames per trigger (in SOFTWARE / HARDWARE modes)
        data_dict['msWait']                 =  data_list[5]  #ms to wait for previous trig to complete before switch
        data_dict['nBurst']                 =  data_list[6]  #number of images to capture on software/external trigger
        return data_dict

    def ZOOCAM_TRIGGER_INFO_tolist(self, data_dict):
        """
        Transform dictionary to list of ZOOCAM_TRIGGER_INFO structure.
        """
        data_list = []
        data_list.append(data_dict['mode']        )
        data_list.append(data_dict['ext_slope']   )
        data_list.append(data_dict['capabilities'])
        data_list.append(data_dict['armed']       )
        data_list.append(data_dict['frames']      )
        data_list.append(data_dict['msWait']      )
        data_list.append(data_dict['nBurst']      )
        return data_list

    def ZOOCAM_TRIGGER_INFO_SEND_tolist(self, data_dict):
        """
        Transform dictionary to list of ZOOCAM_TRIGGER_INFO structure.
        """
        data_list = []
        data_list.append(data_dict['mode']        )
        data_list.append(data_dict['ext_slope']   )
        data_list.append(data_dict['frames']      )
        data_list.append(data_dict['msWait']      )
        data_list.append(data_dict['nBurst']      )
        return data_list
    
    def ZOOCAM_TRIGGER_CAPABILITIES_int2dict(self, cap_int):
        """
        Converts capability integer (bitstring) to dict
        """
        cap_dict = {}
        bitstring = format(cap_int, '#032b')
        cap_dict["Freerun"]                  = bool(int(bitstring[-1]))
        cap_dict["Software"]                 = bool(int(bitstring[-2]))
        cap_dict["External"]                 = bool(int(bitstring[-3]))
        cap_dict["SingleShot"]               = bool(int(bitstring[-4]))
        cap_dict["Burst"]                    = bool(int(bitstring[-5]))
        cap_dict["ArmDisarm"]                = bool(int(bitstring[-6]))
        cap_dict["ForceExtTrigger"]          = bool(int(bitstring[-7]))
        cap_dict["MultipleFramesPerTrigger"] = bool(int(bitstring[-8]))
        cap_dict["ExtTrigSlope"]             = bool(int(bitstring[-9]))
        return cap_dict

    def ZOOCAM_TRIGGER_CAPABILITIES_dict2int(self, cap_dict):
        """
        Converts capability integer (bitstring) to dict
        """
        cap_str = ""
        cap_str += "1" if cap_dict["Freerun"]                  else "0" 
        cap_str += "1" if cap_dict["Software"]                 else "0" 
        cap_str += "1" if cap_dict["External"]                 else "0" 
        cap_str += "1" if cap_dict["SingleShot"]               else "0" 
        cap_str += "1" if cap_dict["Burst"]                    else "0" 
        cap_str += "1" if cap_dict["ArmDisarm"]                else "0" 
        cap_str += "1" if cap_dict["ForceExtTrigger"]          else "0" 
        cap_str += "1" if cap_dict["MultipleFramesPerTrigger"] else "0" 
        cap_str += "1" if cap_dict["ExtTrigSlope"]             else "0" 
        cap_int = int(cap_str[::-1], 2)
        return cap_int

    def get_ZOOCAM_GET_TRIGGER_MODE(self, msg_id):
        """
        Get the current trigger status, as a TRIGGER_INFO structure
        """
        msg = [6, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        #msg_recv[3] should correspond to the trigger mode integer
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.ZOOCAM_TRIGGER_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.ZOOCAM_TRIGGER_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        #Replace here the capability integer to dict
        data_recv_dict['capabilities'] = self.ZOOCAM_TRIGGER_CAPABILITIES_int2dict(data_recv_dict['capabilities'])
        return msg_recv[3], data_recv_dict

    def set_ZOOCAM_SET_TRIGGER_MODE(self, msg_id, trigger_mode = 0, trigger_dict = None):
        """
        Set the trigger mode (trigger_mode, integer), and if provided also settings dict
        (trigger_dict, dictionary). 
        """
        msg = [7, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        msg[2] = trigger_mode
        #If we have trigger_dict, check if the "capabilities" is a dict and convert to list
        if trigger_dict is not None:
            #If trigger_dict is sent, then override the trigger_mode with the one in dict
            self.logger.warning("Overriding trigger_mode with trigger_dict %d, %d", trigger_mode, trigger_dict["mode"])
            msg[2] = trigger_dict["mode"]
            trigger_dict_cp = cp.deepcopy(trigger_dict)
            print(type(trigger_dict['capabilities']))
            if type(trigger_dict['capabilities']) is dict:
                trigger_dict_cp['capabilities'] = self.ZOOCAM_TRIGGER_CAPABILITIES_dict2int(trigger_dict['capabilities'])
            print(trigger_dict_cp)
            trigger_list = self.ZOOCAM_TRIGGER_INFO_tolist(trigger_dict_cp)
            print("Trigger list", trigger_list)
            s_struct, packer = self.ZOOCAM_TRIGGER_INFO_structure_format()
            msg[4] = packer.size
            packed_data, values = self.pack_data(packer, trigger_list)
            if self.crc:
                crc = self.get_crc(packed_data)
                msg[-1] = crc
        #Send comm
        self.comm_send_struct(msg)
        #If we have trigger_dict, send the data too
        if trigger_dict is not None:
            self.sock.sendall(packed_data)
        #Get response
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv):
            print(msg_recv)
        if int(msg_recv[3]) != msg[2]:
            self.logger.error("Failed to set trigger")
        #Get trigger response data
        s_struct, unpacker = self.ZOOCAM_TRIGGER_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.ZOOCAM_TRIGGER_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        #Replace here the capability integer to dict
        data_recv_dict['capabilities'] = self.ZOOCAM_TRIGGER_CAPABILITIES_int2dict(data_recv_dict['capabilities'])
        return msg_recv[3], data_recv_dict



    #Block dealing with TRIGGER_INFO********************************************

    def set_ZOOCAM_ARM(self, msg_id, arm_id = None):
        """
        Options for arm_id:
            TRIG_ARM_QUERY=0
            TRIG_ARM=1
            TRIG_DISARM=2
            TRIG_ARM_UNKNOWN=3
        """
        msg = [8, msg_id, 0, 0, 0]
        if arm_id is not None:
            msg[2] = arm_id
        else:
            #If no arm_id is provided --> query the status
            msg[2] = 0
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Arm status %d", msg_recv[3])
        return msg_recv[3]

    #Block dealing with ZOOCAM_GET_IMAGE_INFO******************************************
    def ZOOCAM_GET_IMAGE_INFO_structure_format(self):
        """
        Returns structure format of the image info.
        """
        s_struct  = "<"
        s_struct += "I "   #Camera type:    CAMERA_UNKNOWN=0, CAMERA_DCX=1, CAMERA_TL=2
        s_struct += "i "   #frame:          Which frame within the ring buffer 
        s_struct += "Q "   #Time of image (seconds w/ ms resolution) (relative Jan 1, 1970)
        s_struct += "d "   #camera_time:    Time of capture from camera clock - units are seconds but epoch undefined
        s_struct += "I "   #image width
        s_struct += "I "   #image height
        s_struct += "I "   #Bytes between each row (allocate pitch*height)
        s_struct += "d "   #Current exposure (ms) 
        s_struct += "d "   #Gamma value 
        s_struct += "d "   #master_gain: Gains in non-linear range [0,100] 
        s_struct += "d "   #red_gain
        s_struct += "d "   #green_gain
        s_struct += "d "   #blue_gain;
        s_struct += "I "   #color_correct_mode; depends on camera, For DCX, 0,1,2,4,8 corresponding to disable, enable, BG40, HQ, IR Auto
        s_struct += "d"    #color_correct_strength;
        return s_struct, struct.Struct(s_struct)

    def ZOOCAM_GET_IMAGE_INFO_todict(self, data_list):
        """
        Transform list to dictionary of ZOOCAM_GET_IMAGE_INFO structure.
        """
        data_dict = {}
        data_dict['type']                    =  data_list[0]  #type:           Camera type
        data_dict['frame']                   =  data_list[1]  #frame:          Which frame within the ring buffer 
        data_dict['image_time']              =  data_list[2]  #time:           Standard UNIX time of image capture (I think it is int32)
        data_dict['camera_time']             =  data_list[3]  #camera_time:    Time of capture from camera clock - units are seconds but epoch undefined
        data_dict['width']                   =  data_list[4]  #image width and height 
        data_dict['height']                  =  data_list[5]  #image width and height 
        data_dict['memory_pitch']            =  data_list[6]  #Bytes between each row (allocate pitch*height)
        data_dict['exposure']                =  data_list[7]  #Current exposure (ms) 
        data_dict['gamma']                   =  data_list[8]  #Gamma value 
        data_dict['master_gain']             =  data_list[9]  #Gains in non-linear range [0,100] 
        data_dict['red_gain']                =  data_list[10]  #red_gain, green_gain, blue_gain;
        data_dict['green_gain']              =  data_list[11] #red_gain, green_gain, blue_gain;
        data_dict['blue_gain']               =  data_list[12] #red_gain, green_gain, blue_gain;
        data_dict['color_correction']        =  data_list[13] #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto, or COLOR_DISABLE=0, COLOR_ENABLE=1, COLOR_BG40=2, COLOR_HQ=3, COLOR_AUTO_IR=4 
        data_dict['color_correction_factor'] =  data_list[14] #color_correction_factor;
        return data_dict

    def ZOOCAM_GET_IMAGE_INFO_tolist(self, data_dict):
        """
        Transform dictionary to list of ZOOCAM_GET_IMAGE_INFO structure.
        """
        data_list = []
        data_list.append(data_dict['type']                   ) #type:           Camera type
        data_list.append(data_dict['frame']                  ) #frame:          Which frame within the ring buffer 
        data_list.append(data_dict['image_time']             ) #time:           Standard UNIX time of image capture (I think it is int32)
        data_list.append(data_dict['camera_time']            ) #camera_time:    Time of capture from camera clock - units are seconds but epoch undefined
        data_list.append(data_dict['width']                  ) #image width and height 
        data_list.append(data_dict['height']                 ) #image width and height 
        data_list.append(data_dict['memory_pitch']           ) #Bytes between each row (allocate pitch*height)
        data_list.append(data_dict['exposure']               ) #Current exposure (ms) 
        data_list.append(data_dict['gamma']                  ) #Gamma value 
        data_list.append(data_dict['master_gain']            ) #Gains in non-linear range [0,100] 
        data_list.append(data_dict['red_gain']               )  #red_gain, green_gain, blue_gain;
        data_list.append(data_dict['green_gain']             ) #red_gain, green_gain, blue_gain;
        data_list.append(data_dict['blue_gain']              ) #red_gain, green_gain, blue_gain;
        data_list.append(data_dict['color_correction']       ) #0,1,2,4,8 ==> disable, enable, BG40, HQ, IR Auto, or COLOR_DISABLE=0, COLOR_ENABLE=1, COLOR_BG40=2, COLOR_HQ=3, COLOR_AUTO_IR=4 
        data_list.append(data_dict['color_correction_factor']) #color_correction_factor;
        return data_list

    def get_ZOOCAM_GET_IMAGE_INFO(self, msg_id, frame_id = None):
        """
        Wrapper function to get image info. 
        If frame_id = None, the last image in the buffer (frame_id = -1) will be selected
        """
        msg = [9, msg_id, 0, 0, 0]
        if self.crc:
            msg.append(0) 
        if frame_id is None:
            msg[2] = -1
        else:
            msg[2] = frame_id
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            if int(msg_recv[3]) == 1:
                self.logger.error("No camera connected!")
            if int(msg_recv[3]) == 2:
                self.logger.error("Frame invalid!")
            if msg_recv[4] == 0:
                return msg_recv[3]
            self.logger.error("Still receiving data")
        s_struct, unpacker = self.ZOOCAM_GET_IMAGE_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        print("Length expected/packer", msg_recv[4], unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.ZOOCAM_GET_IMAGE_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with ZOOCAM_GET_IMAGE_INFO******************************************

    #Block dealing with ZOOCAM_GET_IMAGE_DATA******************************************
    #Block dealing with ZOOCAM_TL_RAW_FILE********************************************
    ####pragma pack(4)
    ###    #define TL_RAW_FILE_MAGIC                    (0x4A7B92CF)
    ###    typedef struct _TL_RAW_FILE_HEADER {
    ###                   int magic;       /* ID indicating this is my file (check endien)  */
    ###                   int header_size;                 /* Size in bytes of this header (n-8 more) */
    ###                   int major_version, minor_version;            /* Header version (currently 1.0) */
    ###                   double ms_expose;     /* Exposure time in ms */
    ###                   double dB_gain;      /* Gain in dB for camera (RGB dont matter) */
    ###                   time_t timestamp;    /* time() of image capture (relative Jan 1, 1970) */
    ###                   double camera_time;   /* Image time based on pixel clock (arbitrary zero)      */
    ###                   int year, month, day; /* Date of capture (human readable, 2024.02.29)          */
    ###                   int hour, min, sec, ms;   /* Time of capture (human readable, 18:00:59.372)    */
    ###                   char camera_model[16]; /* Camera model*/
    ###                   char camera_serial[16]; /* Serial number of camera */
    ###                   int sensor_type;   /* enum (TL_CAMERA_SENSOR_TYPE) of sensor type*/
    ###                   int color_filter;/* enum (TL_COLOR_FILTER_ARRAY_PHASE) of color filter              */
    ###                   int width, height;   /* height and width of image     */
    ###                   int bit_depth;        /* Bits resolution in each pixel                        */
    ###                   int pixel_bytes, image_bytes;    /* Bytes per pixel and bytes total in image  */
    ###                   double pixel_width, pixel_height;   /* Physical dimensions of pixel (in um)    */
    ###    } TL_RAW_FILE_HEADER;
    ####pragma pack()
    def HEAD_ZOOCAM_RAW_IMAGE_DATA_structure_format(self):
        """
        Returns structure format of the header of raw image
        """
        s_struct  = "<"
        s_struct += "I "   # magic; ID indicating this is my file (check endien) (0x4A7B92CF)
        s_struct += "I "   # header_size; Size in bytes of this header (n-8 more)
        s_struct += "I "   # major_version, minor_version;            /* Header version (currently 1.0) */
        s_struct += "I "   # major_version, minor_version;            /* Header version (currently 1.0) */
        s_struct += "d "   # ms_expose: Exposure time in ms
        s_struct += "d "   # dB_gain: Gain in dB for camera (RGB dont matter)
        s_struct += "Q "   # Time of image (seconds w/ ms resolution) (relative Jan 1, 1970)
        s_struct += "d "   # camera_time: Image time based on pixel clock (arbitrary zero)
        s_struct += "I "   # Y
        s_struct += "I "   # M 
        s_struct += "I "   # D
        s_struct += "I "   # h
        s_struct += "I "   # m 
        s_struct += "I "   # s
        s_struct += "I "   # ms
        s_struct += "16s " # Camera model
        s_struct += "16s " # Camera serial number
        s_struct += "I "   # sensor_type: (TL_CAMERA_SENSOR_TYPE) of sensor
        s_struct += "I "   # color_filter: (TL_COLOR_FILTER_ARRAY_PHASE) of color filter  
        s_struct += "I "   # width
        s_struct += "I "   # height
        s_struct += "I "   # bit_depth: Bits resolution in each pixel
        s_struct += "I "   # pixel_bytes: Bytes per pixel
        s_struct += "I "   # image_bytes: Bytes total in image
        s_struct += "d "   # pixel_width: Physical dimensions of pixel (in um)
        s_struct += "d "   # pixel_height: Physical dimensions of pixel (in um)
        return s_struct, struct.Struct(s_struct)

    def HEAD_ZOOCAM_RAW_IMAGE_DATA_todict(self, data_list):
        """
        Transform list to dictionary of HEAD_ZOOCAM_RAW_IMAGE_DATA_structure_format
        """
        data_dict = {}
        data_dict['magic']                     =  data_list[0]  
        data_dict['header_size']               =  data_list[1]  
        data_dict['major_version']             =  data_list[2]  
        data_dict['minor_version']             =  data_list[3]  
        data_dict['exposure']                  =  data_list[4]  
        data_dict['master_gain']               =  data_list[5]  
        data_dict['image_time']                =  data_list[6]  
        data_dict['camera_time']               =  data_list[7]  
        data_dict['year']                      =  data_list[8]  
        data_dict['month']                     =  data_list[9]  
        data_dict['day']                       =  data_list[10]  
        data_dict['hour']                      =  data_list[11]  
        data_dict['min']                       =  data_list[12]  
        data_dict['sec']                       =  data_list[13]  
        data_dict['msec']                      =  data_list[14]  
        data_dict['model']                     =  data_list[15].decode('utf-8', errors = "ignore").split('\x00', 1)[0] 
        data_dict['serial']                    =  data_list[16].decode('utf-8', errors = "ignore").split('\x00', 1)[0] 
        data_dict['type']                      =  data_list[17]  
        data_dict['color_correction']          =  data_list[18]  
        data_dict['width']                     =  data_list[19]  
        data_dict['height']                    =  data_list[20]  
        data_dict['bit_depth']                 =  data_list[21]  
        data_dict['pixel_bytes']               =  data_list[22]  
        data_dict['image_bytes']               =  data_list[23]  
        data_dict['pixel_width']               =  data_list[24]  
        data_dict['pixel_height']              =  data_list[25]  
        return data_dict

    #Block dealing pixel_width: with ZOOCAM_TL_RAW_FILE********************************************
    def ZOOCAM_GET_IMAGE_DATA_structure_format(self, data_size): #Used to be ZOOCAM_GET_CURRENT_IMAGE_structure_format
        """
        Returns structure format of the image data.
        """
        s_struct  = "<"
        s_struct += str(data_size)+"B "
        return s_struct, struct.Struct(s_struct)

    def read_uint12(self, data_chunk):
        """ 
        For little endien
        Returns correctly decoded raw data in 12 bit version
        """
        data = np.frombuffer(data_chunk, dtype=np.uint8)
        fst_uint8, snd_uint8 = np.reshape(data, (data.shape[0] // 2, 2)).astype(np.uint16).T
        uint12 = fst_uint8 + (snd_uint8 << 8)
        return uint12

    def get_ZOOCAM_GET_IMAGE_DATA(self, msg_id, image_info, frame_id = None, get_raw = False, plot = False): #Used to be get_ZOOCAM_GET_CURRENT_IMAGE
        """
        Wrapper function to get image data.
        If frame_id = None, the last image in the buffer (frame_id = -1) will be selected
        If get_raw = True the raw image will be returned
        Note: raw image will be ALWAYS attached to img_raw
        """
        msg = [10, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        if frame_id is None:
            if "frame" in image_info:
                msg[2] = image_info["frame"]
            else:
                msg[2] = -1
        else:
            msg[2] = frame_id
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            if int(msg_recv[3]) == 1:
                self.logger.debug("No camera connected!")
            if int(msg_recv[3]) == 2:
                self.logger.debug("Frame invalid!")
            if msg_recv[4] == 0:
                return msg_recv[3]
            self.logger.debug("Still receiving data")
        data_size = msg_recv[4]
        #Next get the image data
        image_data_raw = self.recv_data_buffered_raw(data_size)
        consistent = self.check_crc(image_data_raw, msg_recv)
        if consistent:
            self.logger.debug("Image data CRC consistent")
        else:
            self.logger.debug("Image data CRC not consistent")
        self.logger.debug("Image data received, %d", data_size)
        #Some nasty image processing stuff to get the correct RGB image
        img_data = self.read_uint12(image_data_raw)
        height = image_info["height"]
        width = image_info["width"]
        img_data = img_data.reshape((height, width))
        bayer_im = img_data.astype(np.uint16)
        # Apply Demosacing (COLOR_BAYER_BG2BGR gives the best result out of the 4 combinations).
        bgr = cv2.cvtColor(bayer_im, cv2.COLOR_BAYER_GB2BGR)  # The result is BGR format with 16 bits per pixel and 12 bits range [0, 2^12-1]. I think the correct one!
        #If it is an BGR image, we have to change it into RGB
        if get_raw:
            #Or the really raw data
            image_info["img"] = bgr
            # Show image for testing (multiply by 16 because imshow requires full uint16 range [0, 2^16-1]).
            if plot:
                cv2.imshow('bgr', cv2.resize(bgr*16, (width, height)))
                cv2.waitKey()
                cv2.destroyAllWindows()
            # Convert to uint8 before saving as JPEG (not part of the conversion).
            #colimg = np.round(bgr.astype(float) * (255/4095))
            #print(colimg)
            #cv2.imwrite("test.png", colimg)
        else:
            bgr_8 = np.uint8(bgr * (255/4095))
            bgr_8 = np.uint8(np.round(bgr.astype(float) * (255/4095)))
            img = Image.fromarray(bgr_8, 'RGB')
            b, g, r = img.split()
            img = Image.merge("RGB", (r, g, b))
            #This is the rgb image uint8
            image_info["img"] = img
            #Or the bgr image mapped onto uint16
            #image_info["img"] = bgr #Would require times 16, cv2.resize(bgr*16, (width, height)))
            if plot:
                plt.imshow(img)
                plt.show()
        image_info["img_raw"] = image_data_raw
        return image_info

    def get_ZOOCAM_RING_IMAGE_N_DATA(self, msg_id, n_data):
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
        head_s_struct, head_unpacker = self.HEAD_ZOOCAM_RING_IMAGE_N_DATA_structure_format()
        head_size = head_unpacker.size
        img_size = data_size - head_size

        #The complete data
        s_struct, unpacker = self.ZOOCAM_RING_IMAGE_N_DATA_structure_format(img_size)
        data_recv = self.recv_data_buffered(unpacker, msg_recv)
        self.logger.debug("Image data received, %d", data_size)

        #Unpack the header data
        data_dict = {}
        data_dict["timestamp"] = data_recv[0]
        data_dict["width"]     = data_recv[1]
        data_dict["height"]    = data_recv[2]
        data_dict["pitch"]     = data_recv[3]
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
    #Block dealing with ZOOCAM_GET_IMAGE_DATA******************************************

    #Block dealing with ZOOCAM_SAVE_FRAME********************************************
    def FILE_FORMAT_toint(self, format_string):
        """
        Supported formats:
            bmp, raw, jpg, png
        Any other format will default to 0!
        """
        if format_string == "bmp":
            file_int = 1
        elif format_string == "raw":
            file_int = 2
        elif format_string == "jpg":
            file_int = 3
        elif format_string == "png":
            file_int = 4
        else:
            print("Non-supported file format, returning to default")
            file_int = 0
        return file_int

    def FILE_SAVE_PARMS_structure_format(self, charlen):
        """
        Returns structure format to set params
        /* Structure used by ZOOCAM_CLIENT to allow changes to exposure */
        """
        s_struct  = "<"
        s_struct += "i"     # frame_index 
        s_struct += "I "    # file format: FILE_DFLT = 0, FILE_BMP=1, FILE_RAW=2, FILE_JPG=3, FILE_PNG=4 
        #s_struct += str(charlen) + "s" # path: string of fixed length 260
        s_struct +=  "260s" # path: string of fixed length 260
        return s_struct, struct.Struct(s_struct)

    def set_ZOOCAM_SAVE_FRAME(self, msg_id, frame_id = None, file_format = None, path = None):
        """
        Save image buffers based on template pathname, and file format
        If frame_id = None, the last image in the buffer (frame_id = -1) will be selected
        If file_format = None, default will be selected (0)
        If path = None, an empty path will be sent
        """
        msg = [11, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        if frame_id is None:
            frame_id_send = -1
        else:
            frame_id_send = frame_id
        msg[2] = frame_id_send
        if path is None:
            path = ""
        path_send = path.encode('utf-8') + b'\x00'
        print(path_send)
        #path_send = path
        if file_format is None:
            file_format_send = 0
        else:
            if type(file_format) is str:
                file_format_send = self.FILE_FORMAT_toint(file_format)
            else:
                file_format_send = file_format
        send_list = [frame_id_send, file_format_send, path_send]
        s_struct, packer = self.FILE_SAVE_PARMS_structure_format(len(path_send))
        msg[4] = packer.size
        packed_data, values = self.pack_data(packer, send_list)
        print("Values", values)
        print("Values", packed_data)
        print("Packed data", binascii.hexlify(packed_data))
        if self.crc:
            crc = self.get_crc(packed_data)
            msg[-1] = crc
        #Send comm
        self.comm_send_struct(msg)
        #Send the data
        self.sock.sendall(packed_data)
        #Get response
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to save frame")
        return msg_recv[3]
    #Block dealing with ZOOCAM_SAVE_FRAME********************************************

    #Block dealing with ZOOCAM_SAVE_ALL********************************************
    def set_ZOOCAM_SAVE_ALL(self, msg_id, file_format = None, path = None):
        """
        Save image buffers based on template pathname, and file format
        If file_format = None, default will be selected (0)
        If path = None, an empty path will be sent
        frame_id will be ignored
        2022-12-09 00:16:53,098 - ClientZOOCAM - INFO - Sending 12:101:0:0:268:4220570854
        2022-12-09 00:16:53,098 - ClientZOOCAM - DEBUG - Sending b'0000000c0000006500000000000000000000010cfb90cce6'
        2022-12-09 00:16:53,752 - ClientZOOCAM - INFO - Received 12:101:0:2:0:4220570854
        2022-12-09 00:16:53,752 - ClientZOOCAM - DEBUG - Received b'0000000c00000065000000000000000200000000fb90cce6'
        2022-12-09 00:16:53,752 - ClientZOOCAM - WARNING - RC value returned non-zero 12, 2:0
        """
        msg = [12, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        frame_id_send = 0
        if path is None:
            path = ""
        path_send = path.encode('utf-8') + b'\x00'
        if file_format is None:
            file_format_send = 0
        else:
            if type(file_format) is str:
                file_format_send = self.FILE_FORMAT_toint(file_format)
            else:
                file_format_send = file_format
        send_list = [frame_id_send, file_format_send, path_send]
        s_struct, packer = self.FILE_SAVE_PARMS_structure_format(len(path_send))
        msg[4] = packer.size
        packed_data, values = self.pack_data(packer, send_list)
        if self.crc:
            crc = self.get_crc(packed_data)
            msg[-1] = crc
        #Send comm
        self.comm_send_struct(msg)
        #Send the data
        self.sock.sendall(packed_data)
        #Get response
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        if int(msg_recv[3]) != 0:
            self.logger.error("Failed to save all frames")
        return msg_recv[3]
    #Block dealing with ZOOCAM_SAVE_ALL********************************************

##    #Block dealing with ZOOCAM_SET_EXPOSURE********************************************
##    #DEPRECATED
##    def ZOOCAM_SET_EXPOSURE_structure_format(self):
##        """
##        Returns structure format for setting exposure.
##        """
##        s_struct  = "<"
##        s_struct += "d " # Exposure time in ms
##        return s_struct, struct.Struct(s_struct)
##
##    def set_ZOOCAM_SET_EXPOSURE(self, msg_id, exposure):
##        """
##        Wrapper function to set exposure.
##        """
##        msg = [6, msg_id, 0, 0, 0] #Command index is 6, length of the subsequently sent data is 8
##        # Prepare settings data
##        s_struct, packer = self.ZOOCAM_SET_EXPOSURE_structure_format()
##        packed_data, values = self.pack_data(packer, [exposure])
##        msg[4] = packer.size
##        if self.crc:
##            crc = self.get_crc(packed_data)
##            msg.append(crc) 
##        self.comm_send_struct(msg)
##        # Send data
##        self.sock.sendall(packed_data)
##        msg_recv = self.comm_recv_struct(msg)
##        if not self.check_msgid(msg_id, msg_recv): return
##        if int(msg_recv[3]) != 0:
##            self.logger.error("Failed to set exposure")
##        return 
##    #Block dealing with ZOOCAM_SET_EXPOSURE********************************************

    #Block dealing with ZOOCAM_RING_INFO********************************************
    def ZOOCAM_RING_INFO_structure_format(self):
        """
        Returns structure format for getting ring info
        """
        s_struct  = "<"
        s_struct += "I " # Number of buffers in the ring
        s_struct += "I " # Number of frames valid since last reset
        s_struct += "I " # index of last buffer used (from events)
        s_struct += "I " # index of currently displayed frame
        return s_struct, struct.Struct(s_struct)

    def ZOOCAM_RING_INFO_todict(self, data_list):
        """
        Transform list to dictionary of ZOOCAM_RING_INFO_structure_format
        """
        data_dict = {}
        data_dict['nSize']                 =  data_list[0]  # Number of buffers in the ring
        data_dict['nValid']                =  data_list[1]  # Number of frames valid since last reset
        data_dict['iLast']                 =  data_list[2]  # index of last buffer used (from events)
        data_dict['iShow']                 =  data_list[3]  # index of currently displayed frame
        return data_dict

    def get_ZOOCAM_RING_GET_INFO(self, msg_id):
        """
        Wrapper function to get ring info
        """
        msg = [13, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        s_struct, unpacker = self.ZOOCAM_RING_INFO_structure_format()
        packed_data = self.sock.recv(unpacker.size)
        self.check_crc(packed_data, msg_recv)
        data_recv = self.unpack_data(unpacker, packed_data)
        data_recv_dict = self.ZOOCAM_RING_INFO_todict(data_recv)
        data_string = ', '.join(['%s:%s' % (key, value) for (key, value) in data_recv_dict.items()])
        self.logger.debug("Received %s", binascii.hexlify(packed_data))
        self.logger.debug("Received %s", data_string)
        return data_recv_dict
    #Block dealing with ZOOCAM_RING_INFO********************************************

    #Block dealing with ZOOCAM_RING_GET_SIZE********************************************
    def get_ZOOCAM_RING_GET_SIZE(self, msg_id):
        """
        Return current number of buffers (maximum frames) in the ring
        """
        msg = [14, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Ring size %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_RING_GET_SIZE********************************************

    #Block dealing with ZOOCAM_RING_SET_SIZE********************************************
    def set_ZOOCAM_RING_SET_SIZE(self, msg_id, ring_size):
        """
        Return current number of buffers (maximum frames) in the ring
        """
        msg = [15, msg_id, 0, 0, 0]
        msg[2] = ring_size
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Ring size set %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_RING_SET_SIZE********************************************

    #Block dealing with ZOOCAM_RING_RESET_COUNT********************************************
    def set_ZOOCAM_RING_RESET_COUNT(self, msg_id, ring_count = None):
        """
        Reset the ring buffer so next image will be in buffer 0
        """
        msg = [16, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        if ring_count is not None:
            msg[2] = ring_count
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Reset ring count %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_RING_GET_FRAME_CNT********************************************
    
    #Block dealing with ZOOCAM_RING_GET_FRAME_CNT********************************************
    def get_ZOOCAM_RING_GET_FRAME_CNT(self, msg_id):
        """
        Returns the number of frames in ring that are active
        """
        msg = [17, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Number of frames in ring %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_RING_GET_FRAME_CNT********************************************


##    #Block dealing with ZOOCAM_RING_IMAGE_N_DATA******************************************
##    def HEAD_ZOOCAM_RING_IMAGE_N_DATA_structure_format(self):
##        """
##        Returns structure format of the image n data
##        """
##        s_struct  = "<"
##        s_struct += "d " # Time of image (seconds w/ ms resolution) 
##        s_struct += "I " # width
##        s_struct += "I " # height
##        s_struct += "I " # pitch
##        return s_struct, struct.Struct(s_struct)
##
##    def ZOOCAM_RING_IMAGE_N_DATA_structure_format(self, data_size):
##        """
##        Returns structure format of the image n data
##        """
##        print("data_size", data_size)
##        s_struct  = "<"
##        s_struct += "d " # Time of image (seconds w/ ms resolution) 
##        s_struct += "I " # width
##        s_struct += "I " # height
##        s_struct += "I " # pitch
##        s_struct += str(data_size)+"B " #width x height data immediately follows
##        return s_struct, struct.Struct(s_struct)
##
##    def get_ZOOCAM_RING_IMAGE_N_DATA(self, msg_id, n_data):
##        """
##        Return image data for frame buffer N (option) 
##        """
##        msg = [12, msg_id, 0, 0, 0]
##        msg[2] = n_data
##        if self.crc:
##           msg.append(0) 
##        self.comm_send_struct(msg)
##        msg_recv = self.comm_recv_struct(msg)
##        print("message received zoomcam ring", msg_recv)
##        if not self.check_msgid(msg_id, msg_recv): return
##        data_size = msg_recv[4]
##
##        #Split image data into head and image data
##        head_s_struct, head_unpacker = self.HEAD_ZOOCAM_RING_IMAGE_N_DATA_structure_format()
##        head_size = head_unpacker.size
##        img_size = data_size - head_size
##        print("raw_data size", data_size)
##
##        #The complete data
##        s_struct, unpacker = self.ZOOCAM_RING_IMAGE_N_DATA_structure_format(img_size)
##        data_recv = self.recv_data_buffered(unpacker, msg_recv)
##        self.logger.debug("Image data received, %d", data_size)
##
##        #Unpack the header data
##        data_dict = {}
##        data_dict["timestamp"] = data_recv[0]
##        data_dict["width"]     = data_recv[1]
##        data_dict["height"]    = data_recv[2]
##        data_dict["pitch"]     = data_recv[3]
##        image_data = data_recv[4:]
##        if data_dict["pitch"] == data_dict["width"]: 
##            image_data = np.uint8(image_data).reshape((data_dict["height"], data_dict["pitch"])) #packed_data
##        #In this case we are dealing with a monochrome image, but we should be careful. 
##        #Might have to get the info from camera itself and not the image 
##            img = Image.fromarray(image_data, 'L')
##        elif data_dict["pitch"] == 3 * data_dict["width"]: 
##        #If it is an BGR image, we have to change it into RGB
##            image_data = np.uint8(image_data).reshape( (data_dict["height"], data_dict["width"], 3)) #packed_data
##            img = Image.fromarray(image_data, 'RGB')
##            b, g, r = img.split()
##            img = Image.merge("RGB", (r, g, b))
##        data_dict["img"]       = img
##        return data_dict
##    #Block dealing with ZOOCAM_RING_IMAGE_N_DATA******************************************

    #Block dealing with ZOOCAM_BURST_ARM********************************************
    def set_ZOOCAM_BURST_ARM(self, msg_id):
        """
        Arm the burst (returns immediately)
        BURST_ARM: 0 if successful (or if already armed)
        """
        msg = [18, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst armed %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_BURST_ARM********************************************

    #Block dealing with ZOOCAM_BURST_ABORT********************************************
    def set_ZOOCAM_BURST_ABORT(self, msg_id):
        """
        Abort awaiting burst (returns immediately)
        BURST_ABORT: 0 if successful (or wasn't armed)
        """
        msg = [19, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst aborted %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_BURST_ABORT********************************************

    #Block dealing with ZOOCAM_BURST_STATUS********************************************
    def get_ZOOCAM_BURST_STATUS(self, msg_id):
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
        msg = [20, msg_id, 0, 0, 0]
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst status %d", msg_recv[3])
        return msg_recv[3]
        return 
    #Block dealing with ZOOCAM_BURST_STATUS********************************************

    #Block dealing with ZOOCAM_BURST_WAIT********************************************
    def set_ZOOCAM_BURST_WAIT(self, msg_id, timeout):
        """
        Wait for burst to complete (request.option = msTimeout)
        BURST_WAIT: 0 if complete, 1 on timeout
        """
        msg = [21, msg_id, 0, 0, 0]
        msg[2] = int(timeout) #In ms
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("Burst wait %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_BURST_WAIT********************************************

    #Block dealing with ZOOCAM_LED_SET_STATE********************************************
    def set_ZOOCAM_LED_SET_STATE(self, msg_id, led_state):
        """
        Set LED current supply either on or off (or query) 
        Option: 0 to turn off
                1 to turn on
                2 to query (same effect for any value not 0 or 1)
        Return value is BOOL:  0 if off, 1 if on. If the state can’t be determined, will return 0 also.
        """
        msg = [22, msg_id, 0, 0, 0]
        msg[2] = led_state
        if self.crc:
           msg.append(0) 
        self.comm_send_struct(msg)
        msg_recv = self.comm_recv_struct(msg)
        if not self.check_msgid(msg_id, msg_recv): return
        self.logger.debug("LED state %d", msg_recv[3])
        return msg_recv[3]
    #Block dealing with ZOOCAM_LED_SET_STATE********************************************

##    #Block dealing with ZOOCAM_VIDEO_ENABLE********************************************
##    def set_ZOOCAM_VIDEO_ENABLE(self, msg_id, led_state):
##        """
##        Set Videa current supply either on or off (or query) 
##        Option: 0 to turn off
##                1 to turn on
##                2 to query (same effect for any value not 0 or 1)
##        Return value is BOOL:  0 if off, 1 if on. If the state can’t be determined, will return 0 also.
##        """
##        msg = [18, msg_id, 0, 0, 0]
##        msg[2] = led_state
##        if self.crc:
##           msg.append(0) 
##        self.comm_send_struct(msg)
##        msg_recv = self.comm_recv_struct(msg)
##        if not self.check_msgid(msg_id, msg_recv): return
##        self.logger.debug("Video state %d", msg_recv[3])
##        return msg_recv[3]
##    #Block dealing with ZOOCAM_VIDEO_ENABLE********************************************

##    #Block dealing with ZOOCAM_SAVE_IMAGE_BUFFERS********************************************
##    def set_ZOOCAM_SAVE_IMAGE_BUFFERS(self, msg_id):
##        """
##        Save image buffers based on template pathname
##        """
##        msg = [19, msg_id, 0, 0, 0]
##        if self.crc:
##           msg.append(0) 
##        self.comm_send_struct(msg)
##        msg_recv = self.comm_recv_struct(msg)
##        if not self.check_msgid(msg_id, msg_recv): return
##        self.logger.debug("Buffer saved %d", msg_recv[3])
##        return msg_recv[3]
##    #Block dealing with ZOOCAM_SAVE_IMAGE_BUFFERS********************************************

    def get_image(self, msg_id, delay = None, camera_info = None, get_raw = False, plot = False, check_settings = False):
        """
        Wrapper function to get an image.
        First aquires the image, then gets the image info, and finally sends
        the image itself back to the client.
        If the camera_info is not provided, then the camera_infor is also
        acquired.
        Some post-processing is performed to return a PIL image data if get_raw = False
        Also, image_info["img"] contains either the raw bgr image, or the uint8
        bitmap image in rgb format
        The raw image will always be returned in image_info["img_raw"]
        If check_settings is True additional checks will be performed to make
        sure that the ringsize is large enough, the camera is armed, trigger succeeded, etc. Might cause overhead
        """
        if delay is not None:
            print("Sleeping before acquiring image")
            time.sleep(delay)
        if camera_info is None:
            camera_info = self.get_ZOOCAM_GET_CAMERA_INFO(msg_id)
        #The acquire image has changed
        trigger_mode = 1 #Software trigger
        recv, trigger_dict = self.get_ZOOCAM_GET_TRIGGER_MODE(msg_id)
        trigger_dict["mode"] = trigger_mode 
        trigger_dict['frames'] = 1 #Number of frames per trigger
        trig_recv, trigger_dict_recv = self.set_ZOOCAM_SET_TRIGGER_MODE(msg_id, trigger_mode = trigger_mode, trigger_dict = trigger_dict)
        #Arm camera
        self.set_ZOOCAM_ARM(msg_id, arm_id = 1)
        if check_settings:
            #In trigger mode 1 the camera should be armed, but here we will check again
            if trig_recv != trigger_mode:
                print(trig_recv)
                self.logger.error('Could not set trigger mode')
                return
            if not trigger_dict_recv["armed"]:
                self.logger.error('Camera is not armed! Exiting')
                return
            #Get ring size
            ring_size = self.get_ZOOCAM_RING_GET_SIZE(msg_id)
            self.logger.debug("Ring size is %d", ring_size)
            if ring_size < 1:
                self.logger.warning("Ring size too small! Increasing it to 10")
                recv = self.set_ZOOCAM_RING_SET_SIZE(msg_id, 10)
            #Reset ring count
            recv = self.set_ZOOCAM_RING_RESET_COUNT(msg_id)
        #Activate trigger (i.e., capture image)
        recv = self.set_ZOOCAM_TRIGGER(msg_id)
        if delay is not None:
            print("Sleeping after acquiring image")
            time.sleep(delay)
        frame_id = -1 #Last frame captured 
        image_info = self.get_ZOOCAM_GET_IMAGE_INFO(msg_id, frame_id = frame_id)
        image_info = self.get_ZOOCAM_GET_IMAGE_DATA(msg_id, image_info, frame_id = frame_id, get_raw = get_raw,  plot = plot)
        if check_settings:
            #Make sure that the count has increased to 1, because we set it to zero before capture
            frame_count = self.get_ZOOCAM_RING_GET_FRAME_CNT(msg_id)
            if frame_count != 1:
                self.logger.error('Camera did not increase frame count, perhaps no image captured')
                return
        return image_info["img"], image_info

    def write_raw_image(self, filename, image_info, camera_info = None):
        """
        Writes raw image in the same format as Mike
        """
        msg_id = 101
        if camera_info is None:
        #Check if self.camera_info exists, otherwise get it from server
            if not hasattr(self, 'camera_info'):
                camera_info = self.get_ZOOCAM_GET_CAMERA_INFO(msg_id)
                self.camera_info = camera_info
            else:
                camera_info = self.camera_info
        #Construct dict for the header
        data_dict = {}
        data_list = []
        data_dict['magic']                     = 1249612495                                ; data_list.append(data_dict['magic']        )
        data_dict['header_size']               = 152                                       ; data_list.append(data_dict['header_size']  )
        data_dict['major_version']             = 1                                         ; data_list.append(data_dict['major_version'])
        data_dict['minor_version']             = 0                                         ; data_list.append(data_dict['minor_version'])
        data_dict['exposure']                  = image_info["exposure"]                    ; data_list.append(data_dict['exposure']     )
        data_dict['master_gain']               = image_info["master_gain"]                 ; data_list.append(data_dict['master_gain']  )
        data_dict['image_time']                = image_info["image_time"]                  ; data_list.append(data_dict['image_time']   )
        data_dict['camera_time']               = image_info["camera_time"]                 ; data_list.append(data_dict['camera_time']  )
        data_dict["year" ]                     = time.localtime(image_info['image_time'])[0]     ; data_list.append(data_dict["year" ]        )
        data_dict["month"]                     = time.localtime(image_info['image_time'])[1]     ; data_list.append(data_dict["month"]        )
        data_dict["day"  ]                     = time.localtime(image_info['image_time'])[2]     ; data_list.append(data_dict["day"  ]        )
        data_dict["hour" ]                     = time.localtime(image_info['image_time'])[3]     ; data_list.append(data_dict["hour" ]        )
        data_dict["min"  ]                     = time.localtime(image_info['image_time'])[4]     ; data_list.append(data_dict["min"  ]        )
        data_dict["sec"  ]                     = time.localtime(image_info['image_time'])[5]     ; data_list.append(data_dict["sec"  ]        )
        data_dict["msec" ]                     = 0                                         ; data_list.append(data_dict["msec" ]        )
        data_dict['model']                     = camera_info["model"].encode('utf-8') + b'\x00'  ; data_list.append(data_dict['model']        )
        data_dict['serial']                    = camera_info["serial"].encode('utf-8') + b'\x00' ; data_list.append(data_dict['serial']       )
        data_dict['type']                      = image_info["type"]                        ; data_list.append(data_dict['type']         )
        data_dict['color_correction']          = image_info["color_correction"]            ; data_list.append(data_dict['color_correction'])
        data_dict['width']                     = image_info["width"]                       ; data_list.append(data_dict['width']        )
        data_dict['height']                    = image_info["height"]                      ; data_list.append(data_dict['height']       )
        data_dict['bit_depth']                 = 12                                        ; data_list.append(data_dict['bit_depth']    )
        data_dict['pixel_bytes']               = 2                                         ; data_list.append(data_dict['pixel_bytes']  )
        data_dict['image_bytes']               = len(image_info["img_raw"])                ; data_list.append(data_dict['image_bytes']  )
        data_dict['pixel_width']               = camera_info['pixel_width']                ; data_list.append(data_dict['pixel_width']  )
        data_dict['pixel_height']              = camera_info['pixel_height']               ; data_list.append(data_dict['pixel_height'] )
        print(data_list)
        s_struct_img, packer_img = self.HEAD_ZOOCAM_RAW_IMAGE_DATA_structure_format()
        packed_data, values = self.pack_data(packer_img, data_list)
        #Write binary
        f = open(filename,"wb")
        f.write(packed_data)
        f.write(image_info["img_raw"])
        f.close()
        return
        
def test_all_functions():
    with open('logging.yaml', 'r') as f:
        log_cfg = yaml.safe_load(f.read())
    logging.config.dictConfig(log_cfg)
    msg_id = 101
    #address = "LSA"
    #address = "Analysis"
    #address = "Local"
    #address = "CHESS"
    #address = "128.253.129.71"
    address =  "128.84.183.184"
    #address =  "128.84.183.3" #2022 spring camera computer
    camera_client = ClientZOOCAMProtocol(connect = True, address = address)
    #lasgo_client = ClientLasGoProtocol_Struct(connect = True, address = address)
    #spec_client = ClientSpecProtocol(connect = True, address = address)
    #focus_client = ClientFocusProtocol(connect = True, address = address)
    lsa = ds.LSA()
    #conditions = lsa.read("generated_lsa_gd.csv")
    try:
        recv = camera_client.get_ZOOCAM_QUERY_VERSION(msg_id)
        print("Version", recv)
        camera_info = camera_client.get_ZOOCAM_GET_CAMERA_INFO(msg_id)
        ##print("Camera info", camera_info)
        ##recv = camera_client.get_ZOOCAM_GET_EXPOSURE_PARMS(msg_id)
        ##print("Exposure params", recv)
        ##exposure_dict = {}
        ##exposure_dict["EXPOSURE"]    = 0.01
        ##exposure_dict["FPS"]         = 8
        ##exposure_dict["GAMMA"]       = 0
        ##exposure_dict["MASTER_GAIN"] = 1.
        ##exposure_dict["RED_GAIN"]    = 0.2
        ##exposure_dict["GREEN_GAIN"]  = 0.2
        ##exposure_dict["BLUE_GAIN"]   = 0.7
        ##params_to_set = {}
        ##params_to_set["EXPOSURE"]    =  False
        ##params_to_set["FPS"]         =  False
        ##params_to_set["GAMMA"]       =  True
        ##params_to_set["MASTER_GAIN"] =  False
        ##params_to_set["RED_GAIN"]    =  True
        ##params_to_set["GREEN_GAIN"]  =  False
        ##params_to_set["BLUE_GAIN"]   =  False
        ##recv = camera_client.set_ZOOCAM_SET_EXPOSURE_PARMS(msg_id, exposure_dict, params_to_set)
        ##recv = camera_client.set_ZOOCAM_TRIGGER(msg_id)
        ##recv, trigger_dict = camera_client.get_ZOOCAM_GET_TRIGGER_MODE(msg_id)
        ##print("Trigger mode", recv, trigger_dict)
        ##trigger_mode = 4
        ##recv, trigger_dict_recv = camera_client.set_ZOOCAM_SET_TRIGGER_MODE(msg_id, trigger_mode)
        ##print("Set trigger mode received", trigger_dict_recv)
        ##trigger_dict["mode"] = 2
        ##trigger_dict["ext_slope"] = 2
        ##trigger_dict["frames"] = 35
        ##recv, trigger_dict_recv = camera_client.set_ZOOCAM_SET_TRIGGER_MODE(msg_id, trigger_mode, trigger_dict = trigger_dict)
        ##print("Set trigger mode received", trigger_dict_recv)
        ##recv, trigger_dict_recv = camera_client.set_ZOOCAM_SET_TRIGGER_MODE(msg_id, trigger_mode, trigger_dict = trigger_dict)
        ##print("Set trigger mode received", trigger_dict_recv)
        ##recv = camera_client.set_ZOOCAM_ARM(msg_id)
        ##print("Arm status current", recv)
        ##recv = camera_client.set_ZOOCAM_ARM(msg_id, arm_id = 2)
        ##print("Arm status set", recv)
        ##image_info = camera_client.get_ZOOCAM_GET_IMAGE_INFO(msg_id, frame_id = -1)
        ##print("Image info", image_info)
        ##recv = camera_client.get_ZOOCAM_GET_IMAGE_DATA(msg_id, image_info, frame_id = -1, get_raw = False)
        ##path = r"C:\Users\LSA\Box\MURI-SARA\Thermoreflectance\path_to_somewhere_new.bmp"
        ###recv = camera_client.set_ZOOCAM_SAVE_FRAME(msg_id, frame_id = -1, file_format = "bmp", path = path)
        ###recv = camera_client.set_ZOOCAM_SAVE_FRAME(msg_id, frame_id = -1, file_format = "bmp")
        ###recv = camera_client.set_ZOOCAM_SAVE_ALL(msg_id, file_format = "bmp", path = path)
        ##recv = camera_client.get_ZOOCAM_RING_GET_INFO(msg_id)
        ##print("Ring info", recv)
        ##recv = camera_client.get_ZOOCAM_RING_GET_SIZE(msg_id)
        ##print("Ring size", recv)
        ##ringsize = 12
        ##recv = camera_client.set_ZOOCAM_RING_SET_SIZE(msg_id, ringsize)
        ##recv = camera_client.set_ZOOCAM_RING_RESET_COUNT(msg_id)
        ##recv = camera_client.set_ZOOCAM_RING_RESET_COUNT(msg_id, 23)
        ##recv = camera_client.get_ZOOCAM_RING_GET_FRAME_CNT(msg_id)
        ##recv = camera_client.get_ZOOCAM_RING_GET_FRAME_CNT(msg_id)
        ##print("Number of frames", recv)
        ##image_info = camera_client.get_ZOOCAM_GET_IMAGE_INFO(msg_id, frame_id = -1)
        ##image_info = camera_client.get_ZOOCAM_GET_IMAGE_DATA(msg_id, image_info, frame_id = -1, get_raw = True)
        ##camera_client.write_raw_image("received_file.raw", image_info, camera_info)
        img, img_info = camera_client.get_image(msg_id, delay = None, camera_info = None, get_raw = False, plot = True, check_settings = False)
        camera_client.write_raw_image("received_file.raw", img_info, camera_info = None)
        


###        recv = camera_client.get_ZOOCAM_GET_EXPOSURE_PARMS(msg_id)
###        exposure_dict = {}
###        exposure_dict["EXPOSURE"]    = 0.01
###        exposure_dict["FPS"]         = 8
###        exposure_dict["GAMMA"]       = 20
###        exposure_dict["MASTER_GAIN"] = 40
###        exposure_dict["RED_GAIN"]    = 30
###        exposure_dict["GREEN_GAIN"]  = 20
###        exposure_dict["BLUE_GAIN"]   = 10
###        params_to_set = {}
###        params_to_set["EXPOSURE"]    =  False
###        params_to_set["FPS"]         =  False
###        params_to_set["GAMMA"]       =  True
###        params_to_set["MASTER_GAIN"] =  False
###        params_to_set["RED_GAIN"]    =  True
###        params_to_set["GREEN_GAIN"]  =  False
###        params_to_set["BLUE_GAIN"]   =  False
###        recv = camera_client.set_ZOOCAM_SET_EXPOSURE_PARMS(msg_id, exposure_dict, params_to_set)
###        recv = camera_client.get_ZOOCAM_QUERY_VERSION(msg_id)
###        camera_info = camera_client.get_ZOOCAM_GET_CAMERA_INFO(msg_id)
###        recv = camera_client.get_ZOOCAM_ACQUIRE_IMAGE(msg_id)
###        image_info = camera_client.get_ZOOCAM_GET_IMAGE_INFO(msg_id)
###        #camera_client.set_ZOOCAM_SET_EXPOSURE(msg_id, 120.0)
###        #camera_client.set_ZOOCAM_SET_GAINS(msg_id, [80, 20, 20, 20])
###        img, img_info= camera_client.get_image(msg_id)
###        if camera_info["color_mode"] == 1:
###            #Greyscale image
###            plt.imshow(img,aspect='auto', cmap='gray', vmin=0, vmax=255)
###        elif camera_info["color_mode"] == 0:
###            #RGB image
###            plt.imshow(img,aspect='auto')
###        #plt.show()
###        recv = camera_client.get_ZOOCAM_GET_EXPOSURE_PARMS(msg_id)
###        recv = camera_client.set_ZOOCAM_SET_EXPOSURE_PARMS(msg_id, recv)
###        recv = camera_client.get_ZOOCAM_RING_INFO(msg_id)
###        recv = camera_client.get_ZOOCAM_RING_GET_SIZE(msg_id)
###        recv = camera_client.set_ZOOCAM_RING_SET_SIZE(msg_id, 5)
###        recv = camera_client.set_ZOOCAM_VIDEO_ENABLE(msg_id, 0)
###        recv = camera_client.set_ZOOCAM_BURST_ARM(msg_id)
###
###        recv = camera_client.get_ZOOCAM_RING_GET_FRAME_CNT(msg_id)
###        recv = camera_client.get_ZOOCAM_RING_IMAGE_N_DATA(msg_id, 0)
###        recv = camera_client.set_ZOOCAM_BURST_ABORT(msg_id)
###        recv = camera_client.get_ZOOCAM_BURST_STATUS(msg_id)
###        recv = camera_client.set_ZOOCAM_BURST_WAIT(msg_id, 5000)
###        recv = camera_client.set_ZOOCAM_LED_SET_STATE(msg_id, 1)
###        recv = camera_client.set_ZOOCAM_VIDEO_ENABLE(msg_id, 1)
###        recv = camera_client.set_ZOOCAM_SAVE_IMAGE_BUFFERS(msg_id)
###        #Camera part ends here
        return


    finally:
        print ('Closing socket')
        camera_client.close_socket()
    
if __name__ == "__main__":

    test_all_functions()

