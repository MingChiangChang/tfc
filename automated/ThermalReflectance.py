import sys
sys.path.insert(1, '../')
import csv
from sara_client import *
from zoocam_client import ClientZOOCAMProtocol
import argparse
import os
import logging
import logging.config
import numpy as np

"""
Command-line tool for thermal reflectance data collection
"""


class collection(object):
    """
    Class for a set of data, so it can be stored in a uniform way.
    """
    def __init__(self, irun = 0, args = None, clients = None, led = "Off"):
        """
        A bunch of default values
        """
        self.irun = irun
        self.led = led
        self.args = args
        self.clients = clients
        self.images = []
        self.msg_id = 101

    def set_camera_ring_size(self):
        """
        Set new ring size from args
        """
        recv = self.clients["camera"].get_ZOOCAM_RING_GET_INFO(self.msg_id)
        print("Ring info", recv)
        recv = self.clients["camera"].get_ZOOCAM_RING_GET_SIZE(self.msg_id)
        print("Current ring size", recv)
        recv = self.clients["camera"].set_ZOOCAM_RING_SET_SIZE(self.msg_id, args.ringsize)
        if recv < 0:
            print("Could not set ring size")
            sys.exit(10)
        else:
            print("Ring size set to", self.args.ringsize)
        return recv
    
    def arm_camera(self):
        """
        Check status of camera, and arm
        """
        #Abort any previous scans
        recv = self.clients["camera"].set_ZOOCAM_BURST_ABORT(self.msg_id)
        #Set up burst
        recv, trigger_dict = self.clients["camera"].get_ZOOCAM_GET_TRIGGER_MODE(self.msg_id)
        trigger_dict["ext_slope"] = 1
        trigger_dict["mode"] = 2
        trigger_dict["frames"] = self.args.frame # Frame pre trigger 
        recv = self.clients["camera"].set_ZOOCAM_SET_TRIGGER_MODE(self.msg_id,
                                                                  trigger_mode=2,
                                                             trigger_dict=trigger_dict)
        #recv = self.clients["camera"].set_ZOOCAM_ARM(self.msg_id, 1)
        #if recv == 0:
        #    print("Camera armed")
        #else:
        #    print("Camera could not be armed")
        #    sys.exit(10)
        return recv
    
    def run_lsa(self, power = None):
        """
        Runs a stripe with given parameters
        """
        recv = self.clients["lasgo"].get_LASGO_GET_ZONE_STRUCT(self.msg_id)
        option = self.clients["lasgo"].option_LASGO_EXECUTE_ZONE_SCAN(1, 0)
        print(recv)
        #recv["Scan"] = 5
        if power is None:
            recv["Power"] = self.args.power
        else:
            recv["Power"] = power
        recv["Dwell"] = self.args.dwell
        if self.args.scanmode == "s":
            recv["Ymin"]  = self.args.posmin[1]
            recv["Ymax"]  = self.args.posmax[1]
            recv["Xmin"]  = self.args.posmin[0]
            recv["Xmax"]  = self.args.posmax[0]
        elif self.args.scanmode == "r":
            recv["Ymin"]  = self.args.yrange[0]
            recv["Ymax"]  = self.args.yrange[1]
            xstripe = self.irun%len(self.args.xrange)
            recv["Xmin"]  = self.args.xrange[xstripe]
            recv["Xmax"]  = self.args.xrange[xstripe]
        print("Scanning at x position", recv["Xmin"]) 

        recv["Units"] = 1 
        recv["Laser"] = 0 
        recs = [recv]

        #Set job parameters
        jobstr = self.clients["lasgo"].get_LASGO_GET_JOB_STRUCT(self.msg_id, 0)
        jobstr["MaxAccel"] = 5.
        jobstr_recv = self.clients["lasgo"].set_LASGO_SET_JOB_STRUCT(self.msg_id, jobstr)
        print("Job setting", jobstr)

        #Set zone
        rec = self.clients["lasgo"].set_LASGO_VALIDATE_ZONE_SCAN(self.msg_id, option, recs[0]) #Should rewrite handling zones (plural)
        if rec !=0:
            print("Lasgo returns that the requested zone cannot be executed. Returning with the return code")
            print("Error code", rec)
            #sys.exit()
        #Execute scan
        recv = self.clients["lasgo"].set_LASGO_EXECUTE_ZONE_SCAN(self.msg_id, option, recs, timeout = 100000)
        if recv == 0:
            print("Scan executed successfully")
        else:
            print("Scan failed!", recv)
            #sys.exit()
        #Additional check here for the status:
        recv_status = self.clients["lasgo"].get_LASGO_QUERY_STATUS(self.msg_id)
        return recv, recv_status

    def save_images(self, file_format, path):
        """
        Save all images in the buffer to path 
        TODO: test if path can include file prefix
        file_format can be in str or int
        Options:
            bmp: "bmp" or 1
            raw: "raw" or 2
            jpg: "jpg" or 3
            png: "png" or 4
        """
        image_info = self.clients['camera'].set_ZOOCAM_SAVE_FRAME(self.msg_id, 1, file_format, path)
        return [image_info]


    def get_header(self, image_info, camera_info):
        data_dict = {}
        data_list = []
        data_dict['magic'] = 1249612495 ;data_list.append(data_dict['magic'])
        data_dict['header_size'] = 152; data_list.append(data_dict['header_size'])
        data_dict['major_version'] = 1; data_list.append(data_dict['major_version'])
        data_dict['minor_version'] = 0; data_list.append(data_dict['minor_version'])
        data_dict['exposure'] = image_info["exposure"]; data_list.append(data_dict['exposure'])
        data_dict['master_gain'] = image_info["master_gain"]; data_list.append(data_dict['master_gain'])
        data_dict['image_time'] = image_info["image_time"]; data_list.append(data_dict['image_time'])
        data_dict['camera_time'] = image_info["camera_time"]; data_list.append(data_dict['camera_time'])
        data_dict["year"] = time.localtime(image_info['image_time'])[0]; data_list.append(data_dict["year" ])
        data_dict["month"] = time.localtime(image_info['image_time'])[1]; data_list.append(data_dict["month"])
        data_dict["day"] = time.localtime(image_info['image_time'])[2]; data_list.append(data_dict["day"])
        data_dict["hour"] = time.localtime(image_info['image_time'])[3]; data_list.append(data_dict["hour"])
        data_dict["min"] = time.localtime(image_info['image_time'])[4]; data_list.append(data_dict["min"])
        data_dict["sec"] = time.localtime(image_info['image_time'])[5]; data_list.append(data_dict["sec"])
        data_dict["msec" ] = 0; data_list.append(data_dict["msec"])
        data_dict['model'] = camera_info["model"].encode('utf-8') + b'\x00'; data_list.append(data_dict['model'])
        data_dict['serial'] = camera_info["serial"].encode('utf-8') + b'\x00'; data_list.append(data_dict['serial'])
        data_dict['type'] = image_info["type"]; data_list.append(data_dict['type'])
        data_dict['color_correction'] = image_info["color_correction"]; data_list.append(data_dict['color_correction'])
        data_dict['width'] = image_info["width"]; data_list.append(data_dict['width'])
        data_dict['height'] = image_info["height"]; data_list.append(data_dict['height'])
        data_dict['bit_depth'] = 12; data_list.append(data_dict['bit_depth'])
        data_dict['pixel_bytes'] = 2; data_list.append(data_dict['pixel_bytes'])
        data_dict['image_bytes'] = len(image_info["img_raw"]); data_list.append(data_dict['image_bytes'])
        data_dict['pixel_width'] = camera_info['pixel_width']; data_list.append(data_dict['pixel_width'])
        data_dict['pixel_height'] = camera_info['pixel_height']; data_list.append(data_dict['pixel_height'])
        s_struct_img, packer_img = self.clients["camera"].HEAD_ZOOCAM_RAW_IMAGE_DATA_structure_format()
        packed_data, values = self.clients["camera"].pack_data(packer_img, data_list)
        return packed_data


    def get_headers_and_images(self):
        """
        Count the collected images, and transfer them
        """
        n_images = self.clients["camera"].get_ZOOCAM_RING_GET_FRAME_CNT(self.msg_id)
                #jprint("Collecting number of images", n_images)
        image_info = self.clients['camera'].get_ZOOCAM_GET_IMAGE_INFO(self.msg_id)
        camera_info = self.clients["camera"].get_ZOOCAM_GET_CAMERA_INFO(self.msg_id)
        #image_info = self.clients['camera'].get_ZOOCAM_GET_IMAGE_DATA(self.msg_id, image_info, get_raw = False,  plot = False)
        print("###################")
        print(n_images, len(image_info))
        print("###################")
        images = []
        headers = []
        for i_image in range(n_images):
            image_info = self.clients['camera'].get_ZOOCAM_GET_IMAGE_INFO(self.msg_id, frame_id=i_image)
            recv = self.clients['camera'].get_ZOOCAM_GET_IMAGE_DATA(self.msg_id, image_info, frame_id=i_image, get_raw = False, plot = False)
            header = self.get_header(recv, camera_info)
            headers.append(header)
            images.append(recv)
            print("Image received index", i_image)
        return headers, images
    
    def set_led(self):
        """
        Switch led on or off, depending on self.led
        """
        if self.led == "On":
            recv = self.clients["camera"].set_ZOOCAM_LED_SET_STATE(self.msg_id, 1)
        elif self.led == "Off":
            recv = self.clients["camera"].set_ZOOCAM_LED_SET_STATE(self.msg_id, 0)
        else:
            print("Setting of the LED is either On or Off")
            sys.exit(10)
        return recv
    
    def get_camera_info(self):
        """
        Get info of camera
        """
        camera_info = self.clients["camera"].get_ZOOCAM_GET_CAMERA_INFO(self.msg_id)
        return camera_info
    
    def plot_image(self, images):
        """
        Plot the image that was collected
        """
        if self.args.plot:
            for image in images:
                pos = [0., 0.]
                xpix = image["width"]
                ypix = image["height"]
                width_img =  xpix 
                height_img = ypix 
                wmin = pos[0] - width_img * 0.0
                wmax = pos[0] + width_img * 1.0
                hmin = pos[1] - height_img * 0.0
                hmax = pos[1] + height_img * 1.0
                if self.camera_info["color_mode"] == 0:
                    #Greyscale image
                    plt.imshow(image["img"], aspect='auto', cmap='gray', extent=[wmin, wmax, hmin, hmax])
                elif self.camera_info["color_mode"] == 1:
                    #RGB image
                    plt.imshow(image["img"],  extent=[wmin, wmax, hmin, hmax], aspect='auto')
                plt.xlabel('Position x (px)')
                plt.ylabel('Position y (px)')
                plt.show()
        return

    def write_file(self, power = None):
        """
        Construct filename string
        """
        prefix = args.prefix
        dn_power = "%06.2f" % self.args.power + "W"
        dn_dwell = str(int(self.args.dwell)).zfill(5) + "us"
        dn = '_'.join((dn_dwell, dn_power))
        rindex = self.irun + self.args.offset
        print("Stripe index for write", rindex)
        fn_run = "Run-" + str(rindex).zfill(4)
        fn_led = "LED-" + self.led
        if power is None:
            if self.args.power > 0. :
                fn_power = "Power-On"
            else:
                fn_power = "Power-Off"
        else:
            if power > 0. :
                fn_power = "Power-On"
            else:
                fn_power = "Power-Off"

        fn_suffix = "png"

        start_index = self.args.framemin
        if self.args.framemax < 0:
            end_index = len(self.images)
        else:
            end_index = min(self.args.framemax, len(self.images))
        print("##########")
        print(start_index, end_index)
        print("#############")
        for i in range(start_index, end_index):
            image = self.images[i]["img_raw"]
            header = self.headers[i]
            fn_img = "Frame-" + str(i).zfill(4)
            fn = '_'.join((fn_run, fn_img))
            # fn = '.'.join((fn, fn_suffix))
            fn = os.path.join(dn, fn)
            fn = os.path.join(prefix, fn)
            #fn = os.path.join(dn, fn_img)
            #fn = os.path.join(prefix, fn)
            print("Writing image to", fn)
            dirname = os.path.dirname(fn)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(fn + '.raw', "bw") as f:
                f.write(header + image)
            #self.clients["camera"].write_raw_image(fn + '.raw', self.images[i])
            #image.save(fn, format="png")

    def run(self, power = None, save_local = False,
            file_format="raw", path=None):
        """
        Generic run script. Will perform a complete cycle, with settings
        defined in self.
        If power is None, the power value from self.args will be used.
        Power == 0. will perfrom a scan with no laser essentiall, collecting
        only images along the scan.
        """
        self.camera_info = self.get_camera_info()
        #Turn LED on/off
        #self.set_led()
        #Set requested ring size
        self.set_camera_ring_size()
        recv_status = {}
        recv_status["queue"] = -1
        recv_status["system"] = -1
        recv = -1
        while recv_status["queue"] != 256 or recv_status["system"] != 0 or recv != 0:
            #Arm camera
            self.arm_camera()
            #Run anneal
            if power is None:
                recv, recv_status = self.run_lsa()
            else:
                recv, recv_status = self.run_lsa(power = power)
            print("status:", recv_status)
            print("recv:", recv)
            if recv_status["queue"] != 256 or recv_status["system"] != 0 or recv != 0:
                print("LasGo status not OK!")
                user_return = self.user_intervention()
                if user_return == 1:
                    print("Will retry anneal")
                    continue
                elif user_return == 2:
                    print("Will continue without retry")
                    break
                else:
                    print("Exiting code")
                    sys.exit(10)
                
        #Get images
        if self.args.savelocal:
            print(f"Saving to {self.args.path}")
            self.save_images(self.args.file_format, self.args.path)    
        else:
            self.headers, self.images = self.get_headers_and_images()
            #Plot images
            self.plot_image(self.images)
            print("###############")
            print(np.array(self.images).shape)
            print("###################")
            #Write files
            if power is None:
                self.write_file()
            else:
                self.write_file(power = power)

    def run_live(self):
        """
        A stripe with LED on and power on
        """
        #self.led = "On"
        self.run()

    def run_dark(self):
        """
        A stripe with LED off and power on. For IR correction
        """
        self.led = "Off"
        self.run()

    def run_blank(self):
        """
        A stripe with LED on and power off. To get the reference reflectance of
        the wafer. Perhaps this run does not have to be repeated nrun times
        """
        self.led = "On"
        self.run(power = 0.)

    def run_dark_blank(self):
        """
        A stripe with LED off and power off. To get the reference reflectance of
        the wafer. Perhaps this run does not have to be repeated nrun times
        """
        self.led = "Off"
        self.run(power = 0.)

    def user_intervention(self):
        """
        Provides option to the user to interfere when anneal failed due to
        laser not online
        """
        print("Execution of anneal failed")
        print("Please select one of the following options:")
        print("1: Retry")
        print("2: Continue")
        print("3: Abort right now")
        while True:
            inp = input('Please enter your choice \n')
            try:
                inp_int = int(inp)
                if inp_int > 0 and inp_int < 4:
                    break
                else:
                    print("Input value not in range")
                    continue
            except:
                print("Input not valid")
                continue
        return inp_int

def parse():
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-pt', '--plot',                   help="Plot on screen every frame taken", action='store_true')
    parser.add_argument('-pre', '--prefix',    type=str,   help="Prefix directory for storing data", default = "")
    parser.add_argument('-a', '--address',                 help="Address of the device", default="CHESS",  choices=['Analysis', 'LSA', 'Local', "CHESS"])
    parser.add_argument('-r', '--ringsize',    type=int,   help="Ring size", default=50)
    parser.add_argument('-p', '--power',       type=float, help="Anneal power", default=0.)
    parser.add_argument('-d', '--dwell',       type=float, help="Dwell time in mus", default=10000.)
    parser.add_argument('-pmin', '--posmin',   type=float, metavar=('Xmin', 'Ymin'), nargs = 2, default = [0., -45.], help="X,Y position of the scan start")
    parser.add_argument('-pmax', '--posmax',   type=float, metavar=('Xmax', 'Ymax'), nargs = 2, default = [0., +45.], help="X,Y position of the scan end")
    parser.add_argument('-yr',   '--yrange',   type=float, metavar=('Ymin', 'Ymax'), nargs = 2, default = [-45., -45.], help="Range to scan along y, Ymin Ymax")
    parser.add_argument('-xr',   '--xrange',   type=float, metavar=('Xi'), nargs='*', default = [0.], help="List of X position to cycle through")
    parser.add_argument('-m',    '--scanmode', type=str,   choices=['r', 's'], default = "s", help="Mode of operation along x: (r) range, (s) stationary")
    parser.add_argument('-fmin', '--framemin', type=int,   help="Lower bound of frame", default=0)
    parser.add_argument('-fmax', '--framemax', type=int,   help="Upper bound of frame (set to -1 to print all)", default=-1)
    parser.add_argument('-f', '--frame', type=int, help="Frames per trigger.", default=30)
    parser.add_argument('-n', '--nruns',       type=int,   help="Number of runs of a stripe", default=1)
    parser.add_argument('-o', '--offset',      type=int,   help="Offset for the index of stripe", default=0)

    parser.add_argument('-sl', '--savelocal', type=bool, default=False, help="Save images locally on Zoocam computer")
    parser.add_argument('-path', '--path', type=str, default=None, help="Path for saving files")
    parser.add_argument('-ff', '--file_format', type=str, default="raw", help="File format of saved images")

    args = parser.parse_args()
    return args

def get_address(args):
    """
    Parse address
    """
    if args.address:
        address = args.address
    else:
        address =  "CHESS"
    logger.info('Running on the following stage: %s', address)
    return address

def get_clients(args):
    """
    Connect to the required clients
    """
    address = get_address(args)
    clients = {}
    try:
        camera_client = ClientZOOCAMProtocol(connect = True, address = address)
        clients["camera"] = camera_client
    except:
        logger.error("Failed to open camera client")
        sys.exit(10)
    try:
        lasgo_client   = ClientLasGoProtocol_Struct(connect = True, address =  address)
        clients["lasgo"] = lasgo_client
    except:
        logger.error("Failed to open lasgo client")
        sys.exit(10)
    return clients
    
if __name__ == "__main__":

    #Initialize logger
    logger = logging.getLogger("CollectSpectraImages")
    logger.setLevel(logging.ERROR)

    #Parse command line arguments
    args = parse()
    
    #Start the required clients here
    clients = get_clients(args)
    
    try:
        for irun in range(args.nruns):
            c = collection(irun = irun, args = args, clients = clients, led = "On")
            #c.arm_camera()
            c.run_live()
            #c.run_dark()
            #c.run_blank()
            #c.run_dark_blank()

    finally:
        for client in clients:
            clients[client].close_socket()
