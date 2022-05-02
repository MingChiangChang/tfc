import sys
sys.path.insert(0, '../src')

import numpy as np
import matplotlib.pyplot as plt

from error_funcs import twod_surface
from temp_calibration import fit_xy_to_z_surface_with_func

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
     plt.title(zlabel)
     plt.show()


if __name__ == "__main__":
    surface_func = twod_surface
    params = [1. for _ in range(6)]
    fits = np.load("/Users/ming/Desktop/ramp_rate.npy")
    for i, zlabel in zip([2, 4, 5, 7], ["heating rate in log10","heat rate width","quench rate in log10","quench rate width"]):
        fit_and_plot(np.log10(fits[:,0]), fits[:,1], fits[:,i], surface_func, params, zlabel, verbose=True)
