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

def fit_and_plot(x, y, z, surface_func, params, zlabel, verbose=False):
     x_grid = np.linspace(np.log10(9), np.log10(350), 10)
     y_grid = np.linspace(28, 63, 10)
     xx, yy = np.meshgrid(x_grid, y_grid)
     fig = plt.figure()
     ax = fig.add_subplot(projection='3d')
     ax.scatter(x, y, z, c=z, cmap='bwr')
     fit, _, _ = fit_xy_to_z_surface_with_func(x, y, z, surface_func, params)
     if verbose:
         print(f"fit for {zlabel} is {fit}")
     plane = surface_func(*fit)
     ax.plot_surface(xx, yy, plane(xx, yy), alpha=0.3)
     ax.set_xlabel("log velocity")
     ax.set_ylabel("Power (W)")
     ax.set_zlabel(zlabel)
     plt.show()

if __name__ == "__main__":
    fit_func = two_lorentz 
    gradient_func = two_lorentz_gradient
    interval = 150
    fits = []

    home = Path.home()
    with open("/Users/ming/Desktop/width_fit.json", 'r') as f:
        all_fits = json.load(f)

    for velo, ka in kappa.items():
        bg_fp = home / "Desktop" / "chess_width" / f"chess_2022_{int(velo)}_bg"
        bg = list(bg_fp.glob('*'))[0]
        bgs = sorted(list(bg.glob('*.raw')))
        bg_data = np.zeros((15, 1200, 1920))
        for idx, bg in enumerate(bgs):
            bg_data[idx] = load_blue(bg)
        bg = np.mean(bg_data, axis=0)
    

        raw_fp = home / "Desktop" / "chess_width" / f"chess_2022_{int(velo)}"
        for dir_path in tqdm(sorted(list(raw_fp.glob('*')))):
            dir_name = os.path.basename(dir_path)
            power = dir_name.split('_')[1]
            power = float(power[:-1])
            fps = sorted(list(dir_path.glob('*.raw')))
            data = np.zeros((15, 1200, 1920))
            
            try:
                all_fits[str(int(velo))][str(power)][idx]
            except KeyError:
                print(f"Cannot find power {power}W for velocity {velo}mm/s.")
                continue

            for idx, fp in enumerate(fps):
                data[idx] = load_blue(fp)

            r = (data-bg)/bg

            for idx, d in enumerate(r):
                location_heat_rate = []
                location_cool_rate = []
                print(velo, power)
                center = int(np.round(all_fits[str(int(velo))][str(power)][idx][1]+Y_MIN))
                for i in range(50):
                    avg = np.mean(d[:, center-125+5*i:center-125+5*(i+1)],
                                  axis=1)      # Average around the center to get better
                    y_center = np.argmax(avg)  # fidelity of the maximum point in y
                    avg = avg[y_center - interval : y_center + interval]
                    x = np.arange(2*interval)
                    err = lambda p: fit_func(*p)(x) - avg # linearly fit the quench
                    fit, _ = leastsq(err, [.05, float(interval), 1.,  1.])
                    grad = gradient_func(*fit)(x)/kappa[float(velo)]/PXL_SIZE*float(velo)
                    location_heat_rate.append(np.max(grad))
                    location_cool_rate.append(np.abs(np.min(grad)))
                x = np.arange(50)
                err = lambda p: oned_gaussian_func(*p)(x) - np.log10(location_heat_rate) 
                fit_heat, _ = leastsq(err, [6., 25., 10.])
                err = lambda p: oned_gaussian_func(*p)(x) - np.log10(location_cool_rate)
                fit_cool, _ = leastsq(err, [6., 25., 10.])
                fit = [float(velo), power, *fit_heat, *fit_cool]
                fits.append(fit)

    fits = np.array(fits)
    surface_func = twod_surface
    params = [1., 1., 1., 1., 1., 1.]
    np.save("/Users/ming/Desktop/ramp_rate", fits)
    # for i, zlabel in zip([2, 4, 5, 7], ["heating rate in log10","heat rate width","quench rate in log10","quench rate width"]):
    #     fit_and_plot(np.log10(fits[:,0]), fits[:,1], fits[:,i], surface_func, params, zlabel, verbose=True)
