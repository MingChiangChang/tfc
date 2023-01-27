from inspect import getfullargspec
import os
import json
import sys
from pathlib import Path
sys.path.insert(0, '../src')

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq
from matplotlib.colors import ListedColormap
from scipy.optimize import leastsq
from sympy.utilities.lambdify import lambdify
from sympy import Symbol, solve

from util import sort_current
from error_funcs import temp_surface, twod_surface, temp_surface_sp, new_temp_surface, linear
from error_funcs import test_new_temp_surface, deg_temp_surface, twod_plane
from temp_calibration import fit_xy_to_z_surface_with_func

def quadratic(a, b):
    return lambda x: a*(x-y_th)**2 + b*(x-y_th) # TODO: Can use optimization to find best y_th

def exponential_fit(e, a):
    return lambda x: a*(x-y_th)**e #+ b*(x-y_th)

def cos_exponent_fit(a, e):
    return lambda x: a*(np.cos((x-50)*np.pi/180))**e

def get_kappa_for(full_d, velo, melt_power):
    t = full_d[np.where(full_d[:,0] == velo)]
    err = lambda p: exponential_fit(*p)(t[:,1]) - t[:,2] 
    pfit, _ = leastsq(err, x0=[1., 1.])
    fit_func = exponential_fit(*pfit)
    kappa = fit_func(melt_power)/1400
    plt.plot(t[:,1], t[:,2])
    plt.plot(t[:,1], exponential_fit(*pfit)(t[:,1]))
    plt.show()
    full_d[np.where(full_d[:,0]==velo), 2] /= kappa

######################## Constant Definition ############################
FPS = 40.
kappa = 0.22/(1410-20) #1.4*10**-4 # just a guess
home = Path.home()
y_th = 0
fit_surface = fit_xy_to_z_surface_with_func
surface_func = test_new_temp_surface 

guess = [0.01 for _ in range(len(getfullargspec(surface_func).args))]

######################## Melting Points ############################
dd = np.array([9, 20, 45, 100, 165])
vv = np.array([10., 20., 30., 40., 50.])
pp = np.array([66.5, 74, 80.5, 86., 91.])
si_melt_temp = np.repeat(1400, pp.shape[0]) 
######################## Load/Preprocess data ############################

full_d = np.load("fit.npy")

################ Fitting for each veloicity ##################
for velo, melt_power in zip(vv, pp):
    get_kappa_for(full_d, velo, melt_power)
#full_d[:,2] /= kappa
pfit, pcov, unc, infodict = fit_surface(np.log10(full_d[:,0]),
                                     full_d[:,1],
                                     full_d[:,2],
                                     surface_func, guess)#, uncertainty=result[:,3])
f = surface_func(*pfit)
x = np.linspace(np.log10(10), np.log10(50), 10)
y = np.linspace(40, 90, 10)
xx, yy = np.meshgrid(x, y)
print(pfit)

fig = plt.figure()
ax = fig.add_subplot(projection='3d')
print(full_d[:,1])
print((f(np.log10(full_d[:,0]), full_d[:,1]) - full_d[:,2])/full_d[:,2])
print(np.mean((f(np.log10(full_d[:,0]), full_d[:,1]) - full_d[:,2])**2))
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(full_d[:,0]), full_d[:,1], full_d[:,2],
           c=full_d[:,2], cmap='bwr')
ax.plot_surface(xx, yy, f(xx, yy), alpha=0.3)
ax.set_xlabel('log velocity')
plt.show()
