'''
For processing repetitive thermoreflectance measurements
'''

from pathlib import Path
import os
import json
import sys
sys.path.insert(0, '../src')

from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
 
from read_raw import load_blue
from new_process import parellel_fitting, Y_MAX, Y_MIN
from error_funcs import two_lorentz


velo_ls = [9, 13, 20, 30, 45, 68, 103, 155, 234, 352]

if __name__ == "__main__":
    all_fits = {} 
    for velo in velo_ls:
        print(velo)
        all_fits[velo] = {}
        bg = Path.home() / 'Desktop' / 'chess_width' / f'chess_2022_{velo}_bg' 
        bg = list(bg.glob('*'))[0]

        bgs = sorted(list(bg.glob('*.raw')))
        bg_data = np.zeros((15, 1200, 1920))
        for idx, bg in enumerate(bgs):
            bg_data[idx] = load_blue(bg)

        bg = np.mean(bg_data, axis=0)

        path = Path.home() / 'Desktop' / 'chess_width' / f'chess_2022_{velo}'#/ '09800us_043.00W'

        for dir_path in tqdm(sorted(list(path.glob('*')))):
            dir_name = os.path.basename(dir_path)
            power = dir_name.split('_')[1] 
            power = float(power[:-1])
            fps = sorted(list(dir_path.glob('*.raw')))
            data = np.zeros((15, 1200, 1920))

            for idx, fp in enumerate(fps):
                data[idx] = load_blue(fp)

            r = (data-bg)/bg
            pfit = parellel_fitting(r)
            pfits =[]
            
            for idx, fit in enumerate(pfit):
                p, xpos = fit
                pfits.append(p)
                fit_func = two_lorentz(*p[:4])
                x = np.arange(Y_MAX-Y_MIN)
                plt.plot(x, r[idx, xpos, Y_MIN:Y_MAX])
                plt.plot(x, fit_func(x))
                plt.savefig(f"/Users/ming/Desktop/Figures/{velo}mm_{power}W_{idx}.png")
                plt.clf()
                plt.close("all")
            all_fits[velo][power] = pfits

    with open("/Users/ming/Desktop/width_fit.json", 'w') as f:
        json.dump(all_fits, f)
    #for p in pfit:
    #    t, _ = p
    #    pfits.append(t)
    #
    #pfits = np.array(pfits)
