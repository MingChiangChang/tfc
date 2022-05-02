import os
import sys
from pathlib import Path
import json
sys.path.insert(0, '../src')

import numpy as np
from scipy.optimize import leastsq
import matplotlib.pyplot as plt

from read_raw import load_blue
from fitting import fit_gaussian, fit_two_lorentz
from error_funcs import two_lorentz, two_lorentz, two_lorentz_gradient

Y_MIN = 800
Y_MAX = 1150
PRED_X_CETNER =485
INTERVAL = 100
KAPPA = 0.0001757

def single_frame_fitting(data):
    t = []
    for j in range(INTERVAL): # This define the search region for peak center
        pfit, _ = fit_gaussian(data[PRED_X_CETNER - INTERVAL//2 + j, Y_MIN:Y_MAX])
        t.append(pfit)
    t = np.array(t)
    fit, _ = fit_gaussian(t[:,0])
    pfit, _ = fit_two_lorentz(data[int(np.round(PRED_X_CETNER - INTERVAL//2 + fit[1])), Y_MIN:Y_MAX])
    return pfit, int(np.round(PRED_X_CETNER - INTERVAL//2 + fit[1]))

def find_position_for_temperature(fit_func, temperatures):
    position = []
    for temp in temperatures:
        err = lambda k: fit_func(k) - temp*KAPPA
        pfit, _ = leastsq(err, 100)
        position.append(pfit[0])
    return position

if __name__ == "__main__":
    home = Path.home()
    raw_fp = Path("/Volumes/Samsung_T5/TR_0412/")
    dir_path = raw_fp / "103mm per sec"
    
    high_temp_raw = dir_path / "5mm_59W_002.raw" 
    low_temp_raw  = dir_path / "5mm_55W_002.raw" 
    high_temp_bg  = dir_path / "5mm_0W_002.raw"
    bg = load_blue(high_temp_bg)
    high_temp = (load_blue(high_temp_raw) - bg) / bg 
    low_temp = (load_blue(low_temp_raw) - bg) / bg
    pfit, ind = single_frame_fitting(high_temp)
    pfit_low, ind_low = single_frame_fitting(low_temp)

    plt.imshow(high_temp)
    plt.title("103mm/s 59W")
    plt.show()
    plt.imshow(low_temp)
    plt.title("103mm/s 55W")
    plt.show()


    temperatures = [1000, 900, 800, 700, 600, 500]
    fit_func = two_lorentz(*pfit)
    positions = find_position_for_temperature(fit_func, temperatures)
    fit_func_low = two_lorentz(*pfit_low)
    positions_low = find_position_for_temperature(fit_func_low, temperatures) 
    
    x = np.arange(350)
    plt.plot(x, high_temp[ind, 800:1150]/KAPPA, label="103mm/s 59W")
    plt.plot(x, fit_func(x)/KAPPA)

    plt.plot(x, low_temp[ind, 800:1150]/KAPPA, label="103mm/s 55W")
    plt.plot(x, fit_func_low(x)/KAPPA)
    plt.scatter(positions, temperatures, c='k', s=60)
    plt.scatter(positions_low, temperatures, c='r', s=60)
    plt.xlabel("x pos (pxl)")
    plt.ylabel("Temperature (C)")
    plt.legend()
    plt.show()

    for i in range(6):
        plt.plot(high_temp[400:600, Y_MIN + int(positions[i])] / KAPPA, label="59W")
        plt.plot(low_temp[400:600, Y_MIN + int(positions_low[i])] / KAPPA, label="55W")
        plt.legend()
        plt.xlabel("x pos (pxl)")
        plt.ylabel("Temperature (C)")
        plt.title(f"{temperatures[i]}C")
        plt.show()
