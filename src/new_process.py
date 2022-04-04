import os
from pathlib import Path
from time import time
import json

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_raw import load_background_series
from preprocess import parrallel_processing_frames
from fitting import fit_gaussian, fit_pv, fit_two_lorentz
from error_funcs import oned_gaussian_func
from util import sort_current, parse_fn, get_current_position_dict, get_fn_fmt, get_cond_from_fn
from util import get_bg_keys_at, is_bg, BG_CURRENT


# TODO: Making script into functions
# TODO: Plotting option
# TODO: Collect and report values
# TODO: Fitting funcs
# TODO: Figure out what velocity will make anneal not enough for reaching equilibrium

### Constants ###
Y_MIN = 500
Y_MAX = 1900
PRED_X_CETNER = 700
INTERVAL = 100

if __name__ == "__main__":
    home = Path.home()
    #box = home / "Library" / "CloudStorage" / "Box-Box"
    #tr = box / "MURI-SARA" / "Thermoreflectance" 
    #raw_fp = tr / "2022.03 Velocity Scans" / "15mm per sec"
    raw_fp = home / "Desktop" / "TR" / "co2"
    dir_paths = raw_fp.glob("50mm per sec")
    
    for dir_path in dir_paths:
        print(f"working on {str(dir_path)}")
        ### getting file path and list of current ###
        current_ls = set() 
        current_position_dict = {}
        fps = sorted(list(dir_path.glob("*.raw")))
        current_position_dict = get_current_position_dict(fps)

        current_ls = list(current_position_dict)
        current_ls.remove(BG_CURRENT)
        current_ls = sorted(current_ls)
        
        t = []
        oned_fits = []

        for current in current_ls:
            position = current_position_dict[current]
            bgs = load_background_series(position, fps) 

            data = []
            for idx, _ in tqdm(enumerate(bgs), desc="Load data"):
                data.append(load_blue(str(dir_path  / 
                         (get_fn_fmt(position, current, str(idx).zfill(3)) + ".raw"))))
            
            ### Process data ### 
            bgs = np.array(bgs)
            data = np.array(data)
            r = (data - bgs)/bgs

            oned_fit = []
            for i in range(r.shape[0]):
                t = []
                for j in range(INTERVAL): # This define the search region for peak center
                    pfit, _ = fit_gaussian(r[i, PRED_X_CETNER - INTERVAL//2 + j, Y_MIN:Y_MAX])
                    t.append(pfit) 
                t = np.array(t)
                fit, _ = fit_gaussian(t[:,0])
                pfit, err = fit_two_lorentz(r[i, int(np.round(PRED_X_CETNER + fit[1])), Y_MIN:Y_MAX])
                oned_fit.append(np.append(pfit, err).tolist()) 
            oned_fits.append(oned_fit)
        
        ### Put data into dictionary and save as json ###
        export_dict = {}
        for idx, fit in enumerate(oned_fits): 
            export_dict[current_ls[idx]] = fit

        with open(f"{str(dir_path)}.json", 'w') as f:
            json.dump(export_dict, f)
