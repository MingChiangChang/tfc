'''
Take the preprocessed results (jsons) and turn them in to temperature profile
'''

from pathlib import Path
import glob
import sys
sys.path.insert(1, '../')
sys.path.insert(1, '/Users/ming/Desktop/Code/tfc/src')
import json
import os

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq

from configure_1113 import Configs
from error_funcs import test_new_temp_surface, twod_surface, cubic_surface
from temp_calibration import fit_xy_to_z_surface_with_func


plt.rcParams.update({
    # Font settings
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica'],
    'text.usetex': False,  # Use TeX rendering if desired
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'Helvetica',
    'mathtext.it': 'Helvetica:italic',
    'mathtext.bf': 'Helvetica:bold',

    # Figure layout
    'figure.figsize': [6.4, 4.8],  # Set default figure size (inches)
    'figure.dpi': 300,             # High resolution for publication

    # Axes and labels
    'axes.labelsize': 14,          # Font size for axes labels
    'axes.titlesize': 12,          # Font size for titles
    'axes.linewidth': 0.8,         # Thinner axes lines

    # Tick parameters
    'xtick.labelsize': 12,          # Font size for x-axis tick labels
    'ytick.labelsize': 12,          # Font size for y-axis tick labels
    'xtick.direction': 'in',       # Tick direction
    'ytick.direction': 'in',
    'xtick.major.size': 4,         # Major tick size
    'ytick.major.size': 4,
    'xtick.minor.size': 2,         # Minor tick size
    'ytick.minor.size': 2,
    'xtick.major.width': 0.8,      # Major tick width
    'ytick.major.width': 0.8,
    'xtick.minor.width': 0.6,      # Minor tick width
    'ytick.minor.width': 0.6,

    # Grid
    'grid.alpha': 0.5,             # Transparency of grid
    'grid.linestyle': '--',        # Dashed grid lines
    'grid.linewidth': 0.5,

    # Legend
    'legend.fontsize': 10,          # Font size for legend
    'legend.frameon': False,       # No frame around the legend
    'legend.loc': 'best',

    # Lines and markers
    'lines.linewidth': 1.0,        # Default line width
    'lines.markersize': 4,         # Marker size

    # Savefig options
    'savefig.dpi': 300,            # Save high-resolution figures
    'savefig.format': 'svg',       # Default save format
    'savefig.bbox': 'tight',       # Fit figure tightly to contents
})

config = Configs()
prop_cycle = plt.rcParams['axes.prop_cycle']
colors = prop_cycle.by_key()['color']
t0 = 20
                
def main():

    full_data = []
    #    0      1          2         3        4       5        6       7 
    # velo, power, peak_mean, peak_std, lw_mean, lw_std, rw_mean, rw_std 

    #    0      1     2           3            4
    # velo, power, peak, left_width, right_width
    for velo in config.VELOCITY:
        for power in config.POWER[velo]:
                        
            json_file = f"1113_analysis/{velo}mm_{power}W.json"
            with open(json_file, 'r') as f:
                d = json.load(f)

            peak = np.mean(np.array(d['peak'])[:, config.FRAME[velo]], axis=0)
            # peak_idx = np.mean(np.array(d['peak_idx'])[:, config.FRAME[velo]], axis=0)
            left_width = np.mean(np.array(d['left_width'])[:, config.FRAME[velo]], axis=0)
            right_width = np.mean(np.array(d['right_width'])[:, config.FRAME[velo]], axis=0)

            data = [velo, power, 
                    peak,
                    left_width,
                    right_width]
            full_data.append(data)
    full_data = np.array(full_data)
    print(full_data.shape)

    # for i in range(10):
    for velo in config.VELOCITY:
        mask = full_data[:,0] == velo
        plt.plot(full_data[mask, 1], full_data[mask, 2], marker='o', label=f"{int(velo)} mm/s")
    # plt.plot(full_data[i*8:(i+1)*8, 1], full_data[i*8:(i+1)*8, 2], marker='o', label=str(config.VELOCITY[i]) + "mm/s")
    plt.legend()
    plt.xlabel("Laser Power (W)")
    plt.ylabel("ΔR/R")
    # plt.savefig("ΔR_R.svg")
    plt.show()

    for i, velo in enumerate(sorted(config.MELT, key=int)):
        print(velo)
        velo_data_arr = full_data[np.where(full_data[:,0]==float(velo))]
        print(full_data)
        #plt.plot(velo_data_arr[:,1], velo_data_arr[:,2])
        err = lambda p: exponential_fit(*p)(velo_data_arr[:,1]) - velo_data_arr[:,2]
        pfit, _ = leastsq(err, [1., 1.])
        fit_func = exponential_fit(*pfit)
        # plt.plot(velo_data_arr[:,1], fit_func(velo_data_arr[:,1]))
        # plt.title(str(velo))
        # plt.show()

        # RT = 24 C
        # err = lambda p: ( fit_func(config.MELT[velo])/p - 1390 
        #                 + fit_func(config.MELT_GOLD[velo])/p - 1037 )
        err = lambda p: fit_func(config.MELT[velo])/p - 1390 
        # err = lambda p: fit_func(config.MELT_GOLD[velo])/p - 1037

        kappa, _ = leastsq(err, [0.00017])
        fit_func = lambda x: exponential_fit(*pfit)(x)/kappa
        print(kappa)
        # kappa = 0.00016429
        # fit_func = lambda x: exponential_fit(*pfit)(x)/kappa

        x = np.arange(30, 60)
        # plt.plot(x, fit_func(x))

        # plt.scatter(velo_data_arr[:,1], velo_data_arr[:,2]/kappa + t0, marker='o', color=colors[i])
        # plt.plot([0], [0], label=f"{velo}mm/s", marker='o', color=colors[i])
        # x = np.linspace(21, config.MELT[velo], 10)
        # plt.plot(x, fit_func(x) + t0)
        # plt.scatter([config.MELT[velo]], 1390 + t0, marker='*', c=colors[i], s=50)


        plt.scatter(velo_data_arr[:,1] / config.MELT[velo], velo_data_arr[:,2]/kappa + t0, marker='o', color=colors[i], label=f"{velo} mm/s")
        # plt.plot([0], [0], label=f"{velo}mm/s", marker='o', color=colors[i])
        x = np.linspace(21, config.MELT[velo], 10)
        # plt.plot(x/ config.MELT[velo], fit_func(x) + t0, linestyle=":")
        # plt.scatter([config.MELT[velo]], 1390 + t0, marker='*', c=colors[i], s=50)
        # plt.title(str(velo) + " mm/s")
        # plt.legend()
        # plt.xlabel("Laser Power (W)")
        # plt.ylabel("Temperature (C)")
        # plt.show()
        full_data[np.where(full_data[:,0]==float(velo)), 2] /= kappa

        velo_data_arr = full_data[np.where(full_data[:,0]==float(velo))]
        fit_func = lambda x: exponential_fit(*pfit)(x)/kappa - 1040
        x_gold, _ = leastsq(fit_func, [40.])
        print("Predicted gold power:", x_gold)

        fit_func = lambda x: exponential_fit(*pfit)(x)/kappa - 1390
        x_gold, _ = leastsq(fit_func, [40.])
        print("Predicted si power:", x_gold)

    velo = list(config.MELT)
    si_melt = [config.MELT[v] for v in velo]
    # #au_melt = [config.MELT_GOLD[v] for v in velo]
    # plt.scatter(si_melt, 1414*np.ones(len(si_melt)), marker='x', c='purple', label='Silicon melt')
    # plt.scatter(au_melt, 1037*np.ones(len(si_melt)), marker='*', c='y', label='Gold melt') 
    plt.ylabel("T$_{peak}$ ($^oC$)")
    # plt.xlabel("Power (W)")
    plt.xlabel("Power / Si Melt Power")
    plt.legend()
    plt.ylim(250, 1500)
    plt.xlim(0.58, 1.00)
    # plt.xlim(25, 85)
    plt.savefig("calibrated_temperature_normalized_power.pdf")
    plt.show()

    pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(full_data[:,0]),
                             full_data[:,1],
                             full_data[:,2],
                             test_new_temp_surface,
                             [1., 1., 1., 1., 1.])

    fit_func = test_new_temp_surface(*pfit)

    x = np.linspace(0.9, 2.7, 20)
    y = np.linspace(30, 85, 20)
    xx, yy = np.meshgrid(x, y)
    zz = fit_func(xx, yy)
    ax = plt.figure().add_subplot(projection='3d')
    mask = np.logical_and(zz > 200, zz < 1500)
    xx, yy, zz = xx[mask], yy[mask], zz[mask]
    ax.scatter(np.log10(full_data[:,0]),
               full_data[:,1],
               zs = full_data[:,2], cmap="inferno", c=full_data[:,2])
    ax.plot_trisurf(xx,
                    yy,
                    zz, alpha=0.4, cmap="inferno")
    ax.set_zlim(300, 1400)
    ax.view_init(elev=20., azim=-15)
    ax.set_xlabel("Velocity (10ˣ mm/s)")
    ax.set_ylabel("Laser Power (W)")
    ax.set_zlabel("Tpeak (°C)")
    
    rmse = np.sqrt(( np.sum((full_data[:,2]
                            - fit_func(np.log10(full_data[:,0]),
                                       full_data[:,1])) **2 ))
                    / full_data.shape[0] )
    std = np.std(full_data[:,2])
    print("pfit:", pfit)
    print("RMSE:", rmse)
    print("STD: ", std)
    print("RMSE/STD: ", rmse/std)

    # plt.savefig("temperature_3d.svg")
    plt.tight_layout()
    plt.show()


    pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(full_data[:,0]),
                                 full_data[:,1],
                                 full_data[:,3],
                                 cubic_surface,
                                 [1., 1., 1., 1., 1., 1., 1., 1.])
    
    fit_func = cubic_surface(*pfit)
    x = np.linspace(0.9, 2.7, 20)
    y = np.linspace(30, 85, 20)
    xx, yy = np.meshgrid(x, y)
    zz = fit_func(xx, yy)
    mask = np.logical_and(zz > 200, zz < 450)
    xx, yy, zz = xx[mask], yy[mask], zz[mask]
    ax = plt.figure().add_subplot(projection='3d')
    ax.scatter(np.log10(full_data[:,0]),
               full_data[:,1],
               zs = full_data[:,3], cmap="inferno", c=full_data[:,3])
    ax.plot_trisurf(xx,
                    yy,
                    zz, alpha=0.4, cmap="inferno")
    ax.set_zlim(200, 450)

    ax.view_init(elev=15., azim=60)
    ax.set_xlabel("Velocity (10ˣ mm/s)")
    ax.set_ylabel("Laser Power (W)")
    ax.set_zlabel("Width parameter (pxl)")
    

    plt.tight_layout()
    # plt.savefig("left_width_3d.svg")
    plt.show()
    rmse = np.sqrt(( np.sum((full_data[:,3]
                            - fit_func(np.log10(full_data[:,0]),
                                       full_data[:,1])) **2 ))
                    / full_data.shape[0] )
    std = np.std(full_data[:,3])
    print("pfit:", pfit)
    print("RMSE:", rmse)
    print("STD: ", std)
    print("RMSE/STD: ", rmse/std)

    pfit, _, _  = fit_xy_to_z_surface_with_func(np.log10(full_data[:,0]),
                             full_data[:,1],
                             full_data[:,4],
                             twod_surface,
                             [1., 1., 1., 1., 1., 1.])

    fit_func = twod_surface(*pfit)
    x = np.linspace(0.9, 2.7, 20)
    y = np.linspace(30, 85, 20)
    xx, yy = np.meshgrid(x, y)
    zz = fit_func(xx, yy)
    mask = np.logical_and(zz > 300, zz < 550)
    xx, yy, zz = xx[mask], yy[mask], zz[mask]
    ax = plt.figure().add_subplot(projection='3d')
    ax.scatter(np.log10(full_data[:,0]),
               full_data[:,1],
               zs = full_data[:,4], cmap="inferno", c=full_data[:,4])
    ax.plot_trisurf(xx,
                    yy,
                    fit_func(xx, yy), alpha=0.4, cmap="inferno")
    ax.set_zlim(300, 550)

    ax.view_init(elev=15., azim=60)
    ax.set_xlabel("Velocity (10ˣ mm/s)")
    ax.set_ylabel("Laser Power (W)")
    ax.set_zlabel("Width parameter (pxl)")
    plt.tight_layout()
    
    # plt.savefig("right_width_3d.svg")
    plt.show()
    rmse = np.sqrt(( np.sum((full_data[:, 4]
                            - fit_func(np.log10(full_data[:,0]),
                                       full_data[:,1])) **2 ))
                    / full_data.shape[0] )
    std = np.std(full_data[:,4])
    print("pfit:", pfit)
    print("RMSE:", rmse)
    print("STD: ", std)
    print("RMSE/STD: ", rmse/std)

def exponential_fit(e, a):
    return lambda x: a*(x)**e #+ b*(x-y_th)

def json_fn_parser(json_fn):
    ''' 103mm_34W_run_0.json '''
    split_fn = json_fn.split('.')[0].split('_')
    
    velo = int(split_fn[0][:-2])
    power = int(split_fn[1][:-1])
    run = int(split_fn[-1])
    return velo, power, run

if __name__ == "__main__":
    main()
