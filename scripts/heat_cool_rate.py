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
from error_funcs import linear, twod_surface, width_surface, two_exp, two_gaussian
from error_funcs import test_new_temp_surface, two_reciprocal,  pearson3_func, two_lorentz
from error_funcs import two_lorentz_gradient, oned_gaussian_func

# target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2, 55.:11}
target = {9.: 24, 25.: 9, 50.: 5, 100.: 3, 353.: 2, 200.: 2}
target = {9.: 27, 13.: 18, 20.: 12, 30.: 8, 45.: 5, 68.: 4, 103: 2, 155: 2, 234: 1, 352:1}

#temp_fit = [0.00928042059, -0.000404355686,  0.0725937223, -0.544852557, 3.55016440]
temp_fit = [ 9.03015256e-03, -1.74216105e-04,  7.42548071e-02, -5.55849208e-01,
  3.56689320e+00]
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

    overall_fits = []
    linear_fits = []
    velo_ls = []

    fit_func = two_lorentz 
    gradient_func = two_lorentz_gradient
    interval = 150
    fits = []
     
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')

    for dir_path in dir_paths:
        velo = os.path.basename(dir_path) 
        velocity = float(velo[:velo.index("mm")])
        velo_ls.append(velocity)
        json_path = raw_fp / f"{velo}_test.json" # Path for fitted parameters 
        
        fps = sorted(list(dir_path.glob("*.raw")))
        current_position_dict = get_current_position_dict(fps)

        with open(json_path, "r") as f:
            d = json.load(f)

        stripe_heat_rate = []
        stripe_cool_rate = []
        for current in tqdm(sorted(list(current_position_dict))):
            frame = target[float(velo[:velo.index("mm")])]
            pos = current_position_dict[current] 
            data = load_blue(dir_path / f"{pos}_{current}_{str(frame).zfill(3)}.raw")
            bg   = load_blue(dir_path / f"{pos}_0W_{str(frame).zfill(3)}.raw")
            r = (data-bg)/bg # delta R/R
            
            location_heat_rate = []
            location_cool_rate = []
            if current in d:
                if int(current[:-1]) > 30:
                    center = int(np.round(d[current][frame][1]+Y_MIN))
                    for i in range(50):
                        avg = np.mean(r[:, center-125+5*i:center-125+5*(i+1)],
                                      axis=1)      # Average around the center to get better
                        y_center = np.argmax(avg)  # fidelity of the maximum point in y
                        avg = avg[y_center - interval : y_center + interval]
                        x = np.arange(2*interval)
                        err = lambda p: fit_func(*p)(x) - avg # linearly fit the quench
                        fit, _ = leastsq(err, [.05, float(interval), 1.,  1.])
                        grad = gradient_func(*fit)(x)/kappa[velocity]/PXL_SIZE*velocity
                        location_heat_rate.append(np.max(grad))
                        location_cool_rate.append(np.abs(np.min(grad)))
                        #fit = [velocity, float(current[:-1]), np.max(grad), abs(np.min(grad))] # Add velocity and current as header
                        #overall_fits.append(fit)
                        #fits.append(fit)
                    x = np.arange(50)
                    # Fit heating rate curve
                    err = lambda p: oned_gaussian_func(*p)(x) - np.log10(location_heat_rate) 
                    fit_heat, _ = leastsq(err, [6., 25., 10.])
                    err = lambda p: oned_gaussian_func(*p)(x) - np.log10(location_cool_rate)
                    fit_cool, _ = leastsq(err, [6., 25., 10.])
                    fit = [velocity, float(current[:-1]), *fit_heat, *fit_cool]
                    fits.append(fit)
                    #stripe_cool_rate.append(location_cool_rate)
                    #stripe_heat_rate.append(location_heat_rate)
        #stripe_cool_rate = np.array(stripe_cool_rate)
        #stripe_heat_rate = np.array(stripe_heat_rate)
        #for idx, _ in enumerate(stripe_cool_rate):
        #    x = np.arange(50)
        #    plt.scatter(x, np.log10(stripe_cool_rate[idx]), label=str(idx))
        #    err = lambda p: oned_gaussian_func(*p)(x) - np.log10(stripe_cool_rate[idx])
        #    fit, _ = leastsq(err, [6., 25., 10.])
        #    fits.append(fit)
        #    qr_fit_func = oned_gaussian_func(*fit)
        #    plt.plot(x, qr_fit_func(x))
        #plt.legend()
        #plt.title(f"{velo} cooling rate")
        #plt.show()

    fits = np.array(fits)
    fits = fits[fits[:,2] < 10]
    #print(fits)
    #plt.plot(fits[:,2])
    #plt.show()
    #plt.plot(fits[:,3])
    #plt.show()
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.scatter(np.log10(fits[:,0]), fits[:,1], fits[:,2])
    plt.show()
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.scatter(np.log10(fits[:,0]), fits[:,1], fits[:,3])
    plt.show()
        #plt.plot(fits[:, 1], np.log10(abs(fits[:, 2]/PXL_SIZE*velocity)), label=velo, marker='o')

        ## Trying to fit the quench rate along a velocity
        #err = lambda pfit: linear(*pfit)(fits[:,1]) - np.log10(abs(fits[:, 2]))
        #pfit, _ = leastsq(err, [1., 1.])
        #linear_fits.append(pfit)
        #fit_func = linear(*pfit)
        #plt.plot(fits[:,1], fit_func(fits[:,1]) )
    #plt.legend()
    #plt.show()
    linear_fits = np.array(linear_fits)
    overall_fits = np.array(overall_fits)
