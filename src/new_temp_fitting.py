from inspect import getfullargspec
import glob
from pathlib import Path
import os
import json

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq
from matplotlib.colors import ListedColormap

from util import sort_current
from temp_calibration import fit_xy_to_z_surface_with_func
from error_funcs import test_new_temp_surface, linear

def exponential_fit(e, a):
    return lambda x: a*(x-y_th)**e #+ b*(x-y_th)

######################## Constant Definition ############################
FPS = 40.
kappa = 1.4*10**-4
home = Path.home()
y_th = 0
fit_surface = fit_xy_to_z_surface_with_func
surface_func = test_new_temp_surface 
path = home / "Desktop" /"TR" / "chess"
path = Path("/Volumes/Samsung_T5/TR_0412")

guess = [0.01 for _ in range(len(getfullargspec(surface_func).args))]
#guess = [1., 1., 0.01, 0.01, 1., 1.]

######################## Melting Points ############################
#dd = np.array([15, 75])
#pp = np.array([61.27669902912587, 83.2238805970102])
#dd = np.array([50, 100])
#pp = np.array([54.6, 60.5])
#dd = np.array([9, 20, 45, 100, 165])
#pp = np.array([49.3, 52.2, 56, 61, 63.5])
dd = np.array([9, 13, 20, 30, 45, 68, 103, 155])
pp = np.array([47.8, 48.5, 52.3, 54.3, 56.3, 57.8, 60, 62.5])
#dd = np.array([9, 13, 20, 30, 45, 68, 103, 155, 234, 352])
#pp = np.array([37.5, 38, 39, 40.5, 42, 43.5, 47, 50, 53.5, 58])
err = lambda pfit: linear(*pfit)(np.log10(dd)) - pp
pfit, _  = leastsq(err, [1., 1.,])
x = np.linspace(np.log10(8), np.log10(380), 100)
melt_func = linear(*pfit)
plt.plot(np.log10(dd), pp, marker='o')
plt.plot(x, melt_func(x)) 
plt.xlabel("log10(velocity)")
plt.ylabel("Power")
plt.show()
# melt = np.array([[15, 61.27669902912587, 1020],
#                  [75, 83.2238805970102, 1020]])
#melt = np.array([[50, 54.6], [100, 60.5]]) 68.: ,
# gold_melt_temp = np.repeat(1020, pp.shape[0])
si_melt_temp = np.repeat(1414, pp.shape[0])
si_melt = np.vstack([dd, pp, si_melt_temp, np.zeros(pp.shape[0]), np.zeros(pp.shape[0])]).T
# rng = {15.: 30, 35.: 30,  75.: 30, 150.: 15, 300.: 8, 55.: 30}
# target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2, 55.: 11}
#rng = {9.: 30, 25.: 30, 200.: 10, 50.: 30, 100.: 21, 353.: 9}
#target = {9.: 23, 25.: 9, 50.: 5, 100.: 3, 353.: 2}#, 200.: 2}
target = {9.: 27, 13.: 18, 20.: 12, 30.: 8, 45.: 5, 68.: 4, 103: 2, 155: 2, 234: 1, 352:1}

full_d = []
for j in path.glob("*.json"):
    with open(j, "r") as f:
        data = json.load(f)
    velo_str = os.path.basename(j)
    velo = float(velo_str[:velo_str.index("mm per")])
    current_ls = list(data)
    current_numeric, current_ls = sort_current(current_ls)
    d = [ [velo, curr, data[current_ls[idx]][target[velo]][0],
                       data[current_ls[idx]][target[velo]][2],
                       data[current_ls[idx]][target[velo]][3]]
            for idx, curr in enumerate(current_numeric)
                 if data[current_ls[idx]][target[velo]][0] < 0.25]
    for i in d:
        full_d.append(i)

result = np.array(full_d)
print(result)
pfits = {}
kappa_ls = []
for velo in list(target):
    t =[]
    for row in result:
        if row[0] == velo:
            t.append([row[1:]])
    t = np.array(t)
    x = t[:,0,0]
    err_func = lambda p: np.ravel(exponential_fit(*p)(x))-t[:, 0, 1]
    pfit, _ = leastsq(err_func, [2., 1.], maxfev=2000)
    pfits[velo] = pfit
    fit_func = exponential_fit(*pfit)
#    xx = np.linspace(np.min(x)-5, np.max(x)+5, 50)
#    plt.plot(xx, exponential_fit(*pfit)(xx), label=str(int(i))+"mm per sec")
#    plt.scatter(x, t[:,0,1])
#plt.legend()
#plt.xlabel("Power (W)")
#plt.ylabel("Projected temperature")
#plt.show()
    
    ########### kappa fit for each velocity ############
    kappa_err = lambda kappa: fit_func(melt_func(np.log10(velo)))/kappa - 1414 
    #kappa_err = lambda kappa: fit_func(pp[dd.tolist().index(velo)])/kappa - 817 
    kappa_fit, _ = leastsq(kappa_err, [0.00014])
    print(velo, kappa_fit)
    kappa_ls.append(kappa_fit[0])
    xx = np.linspace(np.min(x)-5, np.max(x)+5, 50)
    plt.plot(xx, exponential_fit(*pfit)(xx)/kappa_fit, label=str(int(velo))+"mm per sec")
    plt.scatter(x, t[:,0,1]/kappa_fit)
    result[result[:,0]==velo,2] /= kappa_fit
plt.legend()
plt.xlabel("Power (W)")
plt.ylabel("Projected temperature")
plt.show()
   
fits = [pfits[v] for v in pfits]
fits = np.array(fits)
print(fits.shape)
plt.plot(fits[:,0])
plt.show()
plt.plot(fits[:,1])
plt.show()


print(result)
pfit, pcov, infodict = fit_surface(np.log10(result[:,0]),
                                    result[:,1],
                                    result[:,2],
                                    surface_func, guess)#, uncertainty=result[:,3])
fit_func = surface_func(*pfit)
x = np.linspace(np.log10(9), np.log10(380), 20)
y = np.linspace(30, 65, 20)
xx, yy = np.meshgrid(x, y)
print(pfit)
fig = plt.figure()
ax = fig.add_subplot(projection='3d')
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(dd), pp, si_melt_temp, c='r')#c=si_melt_temp, cmap=cmap)
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,2],
           c=result[:,2], cmap='bwr')
#for i in range(result.shape[0]):
#    ax.plot([np.log10(result[i,0]), np.log10(result[i, 0])],
#            [result[i,1], result[i,1]],
#            c='purple')
ax.plot_surface(xx, yy, fit_func(xx, yy), alpha=0.3)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('Temperature (C)')
ax.set_title('Tpeak')
ax.set_zlim(0, 1600)
plt.show()

for i in target:
    t = result[result[:,0]==i]
    plt.plot(t[:,1], t[:,2], marker="o", label="Data")
    x = np.linspace(np.min(t[:,1])-1, 63.5, 50)
    plt.plot(x, fit_func(np.log10(t[0,0]), x), label="Fitted")
    plt.title(f"{int(i)}mm per sec")
    plt.xlabel("Power (W)")
    plt.ylim(300, 1400)
    plt.ylabel("Temperature (C)")
    plt.legend()
    plt.savefig(f"/Users/ming/Desktop/{t[0,0]}.png")
    plt.clf()
    plt.close("all")
print(kappa)
