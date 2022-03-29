import os
from pathlib import Path
import json 

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq
from tqdm import tqdm

from read_raw import load_blue
from new_process import get_current_position_dict
from error_funcs import linear

target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2, 55.:11}
Y_MIN = 350
KAPPA = 1.2*10**-4

PXL_SIZE = 1. * 10** -3 # mm

if __name__ == "__main__":
    home = Path.home()
    raw_fp = home / "Desktop" / "TR"
    dir_paths = raw_fp.glob("*mm per sec")
    

    for dir_path in dir_paths:
        velo = os.path.basename(dir_path) 
        velocity = float(velo[:velo.index("mm")])
        json_path = raw_fp / f"{velo}.json"
        
         
        fps = sorted(list(dir_path.glob("*.raw")))[:-1]
        current_position_dict = get_current_position_dict(fps)
        del current_position_dict['10A']       
        fits = []
        for current in tqdm(sorted(list(current_position_dict))):
            frame = target[float(velo[:velo.index("mm")])]
            pos = current_position_dict[current] 
            data = load_blue(dir_path / f"{pos}_{current}_{str(frame).zfill(3)}.raw")
            bg   = load_blue(dir_path / f"{pos}_10A_{str(frame).zfill(3)}.raw")

            with open(json_path, "r") as f:
                d = json.load(f)

            r = (data-bg)/bg
            if current in d:
                center = int(np.round(d[current][frame][1]+350))
                avg = np.mean(r[:, center-20:center+20], axis=1)
                y_center = np.argmax(avg)
                err = lambda p: linear(*p)(np.arange(100)) - avg[y_center:y_center+100]
                fit, _ = leastsq(err, [1.,1.])
                fit = [float(current[:-1]), *fit]
                fits.append(fit)
                #f = linear(*fit)
                #plt.plot(r[:, center], label=current)
        fits = np.array(fits)
        plt.plot(fits[3:, 0], (abs(fits[3:,1]/KAPPA/PXL_SIZE*velocity)), label=velo, marker='o')
    plt.xlabel("Current(A)")
    plt.ylabel("K/s")
    plt.legend()     
    plt.show()
