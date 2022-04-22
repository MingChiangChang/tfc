import os
import sys
from pathlib import Path
import json 
sys.path.insert(0, '../src/')

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq
from matplotlib.colors import ListedColormap
from tqdm import tqdm

from read_raw import load_blue
from new_process import get_current_position_dict
from temp_calibration import fit_xy_to_z_surface_with_func
from error_funcs import linear, twod_surface, width_surface
from error_funcs import test_new_temp_surface

# target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2, 55.:11}
target = {9.: 24, 25.: 9, 50.: 5, 100.: 3, 353.: 2, 200.: 2}
target = {9.: 27, 13.: 18, 20.: 12, 30.: 8, 45.: 5, 68.: 4, 103: 2, 155: 2, 234: 1, 352:1}

temp_fit = [0.00928042059, -0.000404355686,  0.0725937223, -0.544852557, 3.55016440]

Y_MIN = 800 # 350
KAPPA = 0.0001745872796860533 

# Need different kappa for different velocities
kappa = {9.0: 0.0001757,
       13.0: 0.00017924,
       20.0: 0.00018383,
       30.0: 0.00018588,
       45.0: 0.00017557,
       68.0: 0.00017119,
       103.:  0.00015388,
       155.:  0.00014897,
       234.:  0.00011662,
       352.:  0.00010988 } 

PXL_SIZE = 1.04 * 10** -3 # mm
cmap = ListedColormap(['r', 'g', 'b'])

if __name__ == "__main__":
    home = Path.home()
    raw_fp = home / "Desktop" / "TR" / "co2"
    raw_fp = Path("/Volumes/Samsung_T5/TR_0412")
    dir_paths = raw_fp.glob("*mm per sec")
    
    sort_velo = lambda x: int(os.path.basename(x)[:os.path.basename(x).index('mm')])
    dir_paths = sorted(list(dir_paths), key=sort_velo)

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    
    overall_fits = []
    linear_fits = []
    velo_ls = []

    for dir_path in dir_paths:
        velo = os.path.basename(dir_path) 
        velocity = float(velo[:velo.index("mm")])
        velo_ls.append(velocity)
        json_path = raw_fp / f"{velo}_test.json" # Path for fitted parameters 
        
        fps = sorted(list(dir_path.glob("*.raw")))
        current_position_dict = get_current_position_dict(fps)
        fits = []

        with open(json_path, "r") as f:
            d = json.load(f)

        for current in tqdm(sorted(list(current_position_dict))):
            frame = target[float(velo[:velo.index("mm")])]
            pos = current_position_dict[current] 
            data = load_blue(dir_path / f"{pos}_{current}_{str(frame).zfill(3)}.raw")
            bg   = load_blue(dir_path / f"{pos}_0W_{str(frame).zfill(3)}.raw")


            r = (data-bg)/bg # delta R/R
            
            if current in d:
                center = int(np.round(d[current][frame][1]+Y_MIN))
                avg = np.mean(r[:, center-20:center+20], axis=1) # Average around the center to get better
                y_center = np.argmax(avg)                        # fidelity of the maximum point in y
                err = lambda p: linear(*p)(np.arange(100)) - avg[y_center:y_center+100] # linearly fit the quench
                fit, _ = leastsq(err, [1.,1.])
                fit = [i/kappa[velocity]/PXL_SIZE*velocity for i in fit]
                fit = [velocity, float(current[:-1]), *fit] # Add velocity and current as header
                overall_fits.append(fit)
                fits.append(fit)
                #f = linear(*fit)
                #plt.plot(r[:, center], label=current)
        fits = np.array(fits)
        #plt.plot(fits[:, 1], np.log10(abs(fits[:, 2]/PXL_SIZE*velocity)), label=velo, marker='o')

        ## Trying to fit the quench rate along a velocity
        err = lambda pfit: linear(*pfit)(fits[:,1]) - np.log10(abs(fits[:, 2]))
        pfit, _ = leastsq(err, [1., 1.])
        linear_fits.append(pfit)
        fit_func = linear(*pfit)
        #plt.plot(fits[:,1], fit_func(fits[:,1]) )
    #plt.legend()
    #plt.show()
    linear_fits = np.array(linear_fits)
    overall_fits = np.array(overall_fits)

    ## Fitting the overall surface for quench rate
    pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(overall_fits[:,0]),
                          overall_fits[:,1],
                          np.log10(abs(overall_fits[:, 2])),
                          twod_surface, [1., 1., 1., 1., 1., 1.])
    fit_func = twod_surface(*pfit)
    print(pfit)
    
    ################# Plotting ###################
    x = np.linspace(np.log10(9), np.log10(380), 20)
    y = np.linspace(30, 65, 10)
    xx, yy = np.meshgrid(x, y)
    ax.plot_surface(xx, yy, fit_func(xx, yy), alpha=0.5)
    temp_surface = test_new_temp_surface(*temp_fit)
    p = ax.scatter(np.log10(overall_fits[:, 0]),
               overall_fits[:, 1],
               np.log10(abs(overall_fits[:, 2])),
               c = temp_surface(np.log10(overall_fits[:,0]), overall_fits[:,1]),
               label=velo, cmap='bwr')
    fig.colorbar(p)
    plt.xlabel("log velocity")
    plt.ylabel("Current(A)")
    ax.set_zlabel("K/s")
    plt.title("Quench rate (CHESS)")
    plt.show()
