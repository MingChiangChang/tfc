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
import dill
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

######################## Constant Definition ############################
FPS = 40.
kappa = 1.4*10**-4 # just a guess
home = Path.home()
y_th = 0
fit_surface = fit_xy_to_z_surface_with_func
surface_func = test_new_temp_surface 
path = home / "Desktop" /"TR" / "chess"
path = Path("/Volumes/Samsung_T5/TR_0412/First try")

guess = [0.01 for _ in range(len(getfullargspec(surface_func).args))]

######################## Melting Points ############################
#dd = np.array([15, 75])
#pp = np.array([61.27669902912587, 83.2238805970102])
#dd = np.array([50, 100])
#pp = np.array([54.6, 60.5])
dd = np.array([9, 20, 45, 100, 165])
pp = np.array([49.3, 52.2, 56, 61, 63.5])
# melt = np.array([[15, 61.27669902912587, 1020],
#                  [75, 83.2238805970102, 1020]])
#melt = np.array([[50, 54.6], [100, 60.5]]) 68.: ,
# gold_melt_temp = np.repeat(1020, pp.shape[0])
si_melt_temp = np.repeat(1400, pp.shape[0]) 
# rng = {15.: 30, 35.: 30,  75.: 30, 150.: 15, 300.: 8, 55.: 30}
# target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2, 55.: 11}
#rng = {9.: 30, 25.: 30, 200.: 10, 50.: 30, 100.: 21, 353.: 9}
#target = {9.: 23, 25.: 9, 50.: 5, 100.: 3, 353.: 2}#, 200.: 2}
target = {9.: 27, 13.: 18, 20.: 12, 30.: 8, 45.: 5, 68.: 4, 103: 2, 155: 2, 234: 1, 352:1}

######################## Load/Preprocess data ############################

full_d = []
for j in path.glob("*.json"):
    with open(j, "r") as f:
        data = json.load(f)
    velo_str = os.path.basename(j)
    velo = float(velo_str[:velo_str.index("mm per")])
    current_ls = list(data)
    current_numeric, current_ls = sort_current(current_ls)
    d = [ [velo, curr, data[current_ls[idx]][target[velo]][0], data[current_ls[idx]][target[velo]][2], data[current_ls[idx]][target[velo]][3]]
            for idx, curr in enumerate(current_numeric)
                 if data[current_ls[idx]][target[velo]][0] < 0.25]
    for i in d:
        full_d.append(i)

result = np.array(full_d)
pfits ={} 

################ Fitting for each veloicity ##################
for i in list(target):
    t =[]
    for row in result:
        if row[0] == i:
            t.append([row[1:]])
    t = np.array(t)
    x = t[:-1,0,0]
    plt.scatter(x, (t[:-1,0,1]))
    err_func = lambda p: np.ravel(exponential_fit(*p)(x))-(t[:-1, 0, 1])
    pfit, _ = leastsq(err_func, [1., 1.])
    f = cos_exponent_fit(*pfit)
    xx = np.linspace(np.min(x)-5, np.max(x)+5, 50)
    plt.plot(xx, f(xx))
plt.show() 

for i in list(target):
    t =[]
    for row in result:
        if row[0] == i:
            t.append([row[1:]])
    t = np.array(t)
    x = t[:,0,0] 
    err_func = lambda p: np.ravel(exponential_fit(*p)(x))-t[:, 0, 1] 
    pfit, _ = leastsq(err_func, [2., 1.], maxfev=2000)
    pfits[i] = pfit
    xx = np.linspace(np.min(x)-5, np.max(x)+5, 50)
    plt.plot(xx, exponential_fit(*pfit)(xx)/kappa, label=str(int(i))+"mm per sec")
    plt.scatter(x, t[:,0,1]/kappa)
plt.legend()
plt.xlabel("Power (W)")
plt.ylabel("Projected temperature")
plt.show()

p = np.array([[i, pfits[i][0], pfits[i][1]] for i in pfits])
# p = np.array([[i, pfits[i][0]] for i in pfits])
fits = []
err_func = lambda a: linear(*a)(np.log10(p[:,0])) - p[:,1] 
r = leastsq(err_func, x0=[1., 1.])
fit = linear(*r[0])
plt.scatter(np.log10(p[:,0]), p[:,1])
x = np.arange(1, 2.6, 0.1)
plt.plot(x, fit(x))
plt.title("a in a*(x-x0)^2+b(x-x0)")
plt.xlabel("current in log")
plt.show()
fits.append(r[0])

err_func = lambda a: linear(*a)(np.log10(p[:,0])) - np.log10(p[:,2])
r = leastsq(err_func, x0=[1., 1.])
fit = linear(*r[0])
plt.scatter(np.log10(p[:,0]), np.log10(p[:,2]))
x = np.arange(1, 2.6, 0.1)
plt.plot(x, fit(x))
plt.title("b in a*(x-x0)^2+b(x-x0)")
plt.xlabel("current in log")
plt.show()

t = np.array([[i, target[i]/FPS*i]for i in target])
plt.scatter(np.log10(t[:,0]), t[:,1])
plt.xlabel("current in log")
plt.ylabel("distance after shutter open (mm)")
plt.show()

pfit, pcov, infodict = fit_surface(np.log10(result[:,0]),
                                    result[:,1],
                                    result[:,2],
                                    surface_func, guess)#, uncertainty=result[:,3])
fit_func = surface_func(*pfit)
print(f"pfit: {pfit}")

################### Fitting kappa ##################
def f(scaling): # pylint: disable=C0116
    return fit_func(np.log10(dd), pp)/scaling - si_melt_temp

kappa, pcov, infodict, errmsg, success = leastsq(f, [1],
                                          full_output=1)

################### Plotting ######################
x = np.linspace(np.log10(9), np.log10(380), 20)
y = np.linspace(30, 65, 20)
xx, yy = np.meshgrid(x, y)

fig = plt.figure()
ax = fig.add_subplot(projection='3d')

cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(dd), pp, si_melt_temp, c='r')#c=si_melt_temp, cmap=cmap)
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,2]/kappa[0],
           c=result[:,2]/kappa[0], cmap='bwr')
#for i in range(result.shape[0]):
#    ax.plot([np.log10(result[i,0]), np.log10(result[i, 0])],
#            [result[i,1], result[i,1]],
#            c='purple')
ax.plot_surface(xx, yy, fit_func(xx, yy)/kappa[0], alpha=0.3)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('Temperature (C)')
ax.set_title('Tpeak')
ax.set_zlim(0, 1600)
plt.show()

for i in target:
    t = result[result[:,0]==i]
    plt.plot(t[:,1], t[:,2]/kappa[0], marker="o", label="Data")
    x = np.linspace(np.min(t[:,1])-1, np.max(t[:,1])+1, 50)
    plt.plot(x, fit_func(np.log10(t[0,0]), x)/kappa[0], label="Fitted")
    plt.title(f"{int(i)}mm per sec")
    plt.xlabel("Power (W)")
    plt.ylabel("Temperature (C)")
    plt.legend()
    plt.savefig(f"/Users/ming/Desktop/{t[0,0]}_old.png")
    plt.clf()
    plt.close("all")
print(kappa)

t = (pfit/kappa).tolist()
t_func = surface_func(*t)

x = np.linspace(np.log10(9), np.log10(380), 20)
y = np.linspace(30, 65, 10)
xx, yy = np.meshgrid(x, y)

fig = plt.figure()
ax = fig.add_subplot(projection='3d')

cmap = ListedColormap(['r', 'g', 'b'])
#ax.scatter(np.log10(dd), pp, si_melt_temp, c=si_melt_temp, cmap=cmap)

pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(result[:,0]),
                                           result[:,1], result[:,3],
                                           twod_plane, [1., 1., 1.])
fit_func = twod_plane(*pfit)
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,3],
           c=result[:,3], cmap='bwr')
ax.plot_surface(xx, yy, fit_func(xx, yy), alpha=0.3)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('Pixels')
ax.set_title('Left width')
ax.set_zlim(100, 200)
plt.show()

x = np.linspace(np.log10(9), np.log10(380), 20)
y = np.linspace(30, 65, 10)
xx, yy = np.meshgrid(x, y)

fig = plt.figure()
ax = fig.add_subplot(projection='3d')

cmap = ListedColormap(['r', 'g', 'b'])
#ax.scatter(np.log10(dd), pp, si_melt_temp, c=si_melt_temp, cmap=cmap)
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,4],
           c=result[:,4], cmap='bwr')
#ax.plot_surface(xx, yy, fit_func(xx, yy)/kappa[0], alpha=0.3)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('Pixels')
ax.set_title('Right width')
ax.set_zlim(100, 200)
plt.show()


