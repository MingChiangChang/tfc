import os
from time import time
from pathlib import Path
from time import time
from multiprocessing import Pool
import sys
import json
sys.path.insert(0, '../src')

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_raw import load_background_series, load_blue
from preprocess import parrallel_processing_frames
from fitting import fit_gaussian, fit_pv, fit_two_lorentz
from error_funcs import oned_gaussian_func, two_lorentz
from util import sort_current, parse_fn, get_current_position_dict, get_fn_fmt, get_cond_from_fn
from util import get_bg_keys_at, is_bg, BG_CURRENT

### Constants ###
Y_MIN = 800
Y_MAX = 1150
PRED_X_CETNER =485 
INTERVAL = 100


################# Helper funcs for parrerllization ######################
def single_frame_fitting(data):
    t = []
    for j in range(INTERVAL): # This define the search region for peak center
        pfit, _ = fit_gaussian(data[PRED_X_CETNER - INTERVAL//2 + j, Y_MIN:Y_MAX])
        t.append(pfit)
    t = np.array(t)
    fit, _ = fit_gaussian(t[:,0])
    pfit, err = fit_two_lorentz(data[int(np.round(PRED_X_CETNER - INTERVAL//2 + fit[1])), Y_MIN:Y_MAX])
    return np.append(pfit, err).tolist(), int(np.round(PRED_X_CETNER - INTERVAL//2 + fit[1]))

def parellel_fitting(data):
    with Pool() as pool:
        pfit = pool.map(single_frame_fitting, data)
        return pfit

if __name__ == "__main__":
    home = Path.home()
    raw_fp = Path("/Volumes/Samsung_T5/TR_0412/")
    dir_paths = raw_fp.glob("*mm per sec")
    
    for dir_path in dir_paths:
        print(f"working on {str(dir_path)}")
        ####### getting file path and list of current #####3###
        current_ls = set() 
        current_position_dict = {}
        fps = sorted(list(dir_path.glob("*.raw")))
        current_position_dict = get_current_position_dict(fps)

        current_ls = list(current_position_dict)
        current_ls.remove(BG_CURRENT)
        current_ls = sorted(current_ls)
        
        t = []
        oned_fits = []

        for current in tqdm(current_ls):
            position = current_position_dict[current]
            bgs = load_background_series(position, fps) 

            data = []
            for idx, _ in enumerate(bgs):
                data.append(load_blue(str(dir_path  / 
                         (get_fn_fmt(position, current, str(idx).zfill(3)) + ".raw"))))
               
            ######### Process data #########3
            bgs = np.array(bgs)
            data = np.array(data)
            r = (data - bgs)/bgs
 
            result = parrerllel_fitting(r)
            oned_fit = [] 
            # oned_fits.append(oned_fit)
            for idx, fit in enumerate(result):
                pfit, xpos = fit
                oned_fit.append(pfit)
                fit_func = two_lorentz(*pfit[:4]) 
                x = np.arange(Y_MAX-Y_MIN) 
                plt.plot(x, r[idx, xpos, Y_MIN:Y_MAX])
                plt.plot(x, fit_func(x))
                plt.savefig(f"/Users/ming/Desktop/Figures/{os.path.basename(dir_path)}_{current}_{idx}.png")
                plt.clf()
                plt.close("all")
            oned_fits.append(oned_fit)

        
        ############ Put data into dictionary and save as json #########
        export_dict = {}
        for idx, fit in enumerate(oned_fits): 
            export_dict[current_ls[idx]] = fit

        with open(f"{str(dir_path)}_test.json", 'w') as f:
            json.dump(export_dict, f)
