import os
from pathlib import Path
from time import time
import json

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_raw import Color, get_interpolation, read_uint12
from preprocess import parrallel_processing_frames
from fitting import fit_gaussian, fit_pv
from error_funcs import oned_gaussian_func

BG_CURRENT = "10A"
# TODO: Making script into functions
# TODO: Plotting option
# TODO: Collect and report values
# TODO: Fitting funcs
# TODO: Figure out what velocity will make anneal not enough for reaching equilibrium

def load_blue(fp: str):
    with open(fp, 'br') as f:
        data = f.read()

    val = read_uint12(data[152:])
    val = val.reshape(1200, 1920)
    return get_interpolation(val, Color.Blue)
   

def parse_fn(fn: str):
    if '/' in str(fn):
        fn = os.path.basename(fn)
    assert fn[-4:] == ".raw", f"{os.path.basename(fn)} is not a raw file." 
    position, current, frame_num = fn[:-4].split('_')
    return position, current, frame_num 

def get_current_position_dict(fps):
    current_position_dict = {}
    for _fp in list(fps):
        position, current, _ = parse_fn(str(_fp))
        if current not in current_position_dict:
            current_position_dict[current] = position   
    return current_position_dict

def is_bg(current: str):
    return current == BG_CURRENT

def get_fn_fmt(position: str, current: str, frame_num: str):
    return f"{position}_{current}_{frame_num}"

def get_cond_from_fn(fn: str):
    if fn.endswith(".raw"):
        fn = fn[:-4]
    position, current, frame_num = fn.split('_')
    return position, current, frame_num

def get_bg_keys_at(position: str, dict_keys: list):
    bg_keys = []
    for key in keys:
        position, current, frame_num = get_cond_from_key(key)
        if position in key and is_bg(current):
            bg_key.append(key)
    return sorted(bg_keys)

def load_background_series(position: str, fps: list):
    bg_ls = []
    bg_data = []
    for fp in fps:
        _position, current, _ = parse_fn(fp)
        if is_bg(current) and position == _position:
            bg_ls.append(fp)

    for bg in tqdm(sorted(bg_ls), desc = f"Loading background at {position}"):
        bg_data.append(load_blue(bg))  

    return bg_data


if __name__ == "__main__":
    home = Path.home()
    #box = home / "Library" / "CloudStorage" / "Box-Box"
    #tr = box / "MURI-SARA" / "Thermoreflectance" 
    #raw_fp = tr / "2022.03 Velocity Scans" / "15mm per sec"
    raw_fp = home / "Desktop" / "TR"
    dir_paths = raw_fp.glob("55mm per sec")
    for dir_path in dir_paths:
        print(f"working on {str(dir_path)}")
        current_ls = set() 
        current_position_dict = {}
        fps = sorted(list(dir_path.glob("*.raw")))[:-1]
        current_position_dict = get_current_position_dict(fps)
        # fns = list(map(lambda x: str(os.path.basename(x)), fps))

        current_ls = list(current_position_dict)
        current_ls.remove("10A")
        current_ls = sorted(current_ls)
        # Construct background series for each position
        
        t = []
        oned_fits = []
        for current in current_ls:
            position = current_position_dict[current]
            bgs = load_background_series(position, fps) 

            data = []
            for idx, _ in tqdm(enumerate(bgs)):
                data.append(load_blue(str(dir_path  / 
                         (get_fn_fmt(position, current, str(idx).zfill(3)) + ".raw"))))
            
            bgs = np.array(bgs)
            data = np.array(data)
            r = (data - bgs)/bgs
            oned_fit = []
            for i in range(r.shape[0]):
                t = []
                for j in range(100):
                    pfit, _ = fit_gaussian(r[i, 600+j, 350:1600])
                    t.append(pfit) 
                t = np.array(t)
                fit, _ = fit_gaussian(t[:,0])
                pfit, err = fit_gaussian(r[i, int(np.round(600+fit[1])), 350:1600])
                oned_fit.append(np.append(pfit, err).tolist()) 
            oned_fits.append(oned_fit)
            
        export_dict = {}
        for idx, fit in enumerate(oned_fits): 
            export_dict[current_ls[idx]] = fit

        with open(f"{str(dir_path)}.json", 'w') as f:
            json.dump(export_dict, f)
