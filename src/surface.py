from inspect import getfullargspec
import os
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from util import sort_current
from error_funcs import temp_surface, twod_surface, temp_surface_sp, new_temp_surface, linear
from temp_calibration import fit_xy_to_z_surface_with_func
from scipy.optimize import leastsq
from matplotlib.colors import ListedColormap
from scipy.optimize import leastsq

def quadratic(a, b):
    return lambda x: a*(x-12.6)**2 + b*(x-12.6) # TODO: Can use optimization to find best xth
# TODO: Set the trigger to the exact position for exposure
# TODO: The log-linear + quadratic is probably pretty good
# TODO: Any place to put the room temperature?? First thought, always use delat T

FPS = 40.
kappa = 1.4*10**-4
home = Path.home()
dd = np.array([15, 75])
pp = np.array([61.27669902912587, 83.2238805970102])
melt = np.array([[15, 61.27669902912587, 1020],
                 [75, 83.2238805970102, 1020]])
si_melt_temp = np.repeat(1020, pp.shape[0])
rng = {15.: 30, 35.: 30,  75.: 30, 150.: 15, 300.: 8}#, 55.: 30}
target = {15.: 28, 35: 16, 75.: 7, 150.: 4, 300.: 2}#, 55.: 11}
path = home / "Desktop" /"TR"
fit_surface = fit_xy_to_z_surface_with_func
surface_func = new_temp_surface 
guess = [1 for _ in range(len(getfullargspec(surface_func).args))]

#fig = plt.figure()
#ax = plt.axes(projection='3d')
full_d = []
for j in path.glob("*.json"):
    with open(j, "r") as f:
        data = json.load(f)
    velo_str = os.path.basename(j)
    velo = float(velo_str[:velo_str.index("mm per")])
    current_ls = list(data)
    current_numeric, current_ls = sort_current(current_ls)
    d = [ [velo, curr, data[current_ls[idx]][target[velo]][0], data[current_ls[idx]][target[velo]][3]]
            for idx, curr in enumerate(current_numeric)
                 if  data[current_ls[idx]][target[velo]][0] < 0.2]
    for i in d:
        full_d.append(i)
    #ax.scatter(d[:, 0], d[:, 1],d[:,2]/kappa, c=d[:, 2]/kappa)
result = np.array(full_d)
result = result[np.logical_and(result[:,2]<0.18, result[:,2]>0.025)]
pfits ={} 
for i in list(target):
    t =[]
    for row in result:
        if row[0] == i:
            t.append([row[1:]])
    t = np.array(t)
    x = t[2:,0,0] 
    err_func = lambda p: np.ravel(quadratic(*p)(x))-t[2:,0,1] 
    pfit, _ = leastsq(err_func, [1., 1.])
    pfits[i] = pfit
    plt.plot(x, quadratic(*pfit)(x)/kappa, label=str(int(i))+"A")
    plt.scatter(x, t[2:,0,1]/kappa)
plt.legend()
plt.xlabel("Current (A)")
plt.ylabel("Projected temperature")
plt.show()

p = np.array([[i, pfits[i][0], pfits[i][1]] for i in pfits])
# p = np.array([[i, pfits[i][0]] for i in pfits])


err_func = lambda a: linear(*a)(np.log10(p[:,0])) - p[:,1] 
r = leastsq(err_func, x0=[1., 1.])
fit = linear(*r[0])
plt.scatter(np.log10(p[:,0]), p[:,1])
x = np.arange(1, 2.6, 0.1)
plt.plot(x, fit(x))
plt.title("a in a*(x-x0)^2+b(x-x0)")
plt.xlabel("current in log")
plt.show()

err_func = lambda a: linear(*a)(np.log10(p[:,0])) - p[:,2]
r = leastsq(err_func, x0=[1., 1.])
fit = linear(*r[0])
plt.scatter(np.log10(p[:,0]), p[:,2])
x = np.arange(1, 2.6, 0.1)
plt.plot(x, fit(x))
plt.title("b in a*(x-x0)^2+b(x-x0)")
plt.xlabel("current in log")
plt.show()
#
## time
t = np.array([[i, target[i]*0.025*i]for i in target])
plt.scatter(np.log10(t[:,0]), t[:,1])
plt.xlabel("current in log")
plt.ylabel("distance after shutter open (mm)")
plt.show()


pfit, pcov, infodict = fit_surface(np.log10(result[:,0]),
                                    result[:,1],
                                    result[:,2],
                                    surface_func, guess)#, uncertainty=result[:,3])
#plt.show()
fit_func = surface_func(*pfit)

################### Fitting kappa ##################
def f(scaling): # pylint: disable=C0116
    return fit_func(np.log10(dd), pp)/scaling - si_melt_temp

kappa, pcov, infodict, errmsg, success = leastsq(f, [1],
                                          full_output=1)

################### Plotting ######################
x = np.linspace(np.log10(15), np.log10(300), 20)
y = np.linspace(20, 110, 10)
xx, yy = np.meshgrid(x, y)

fig = plt.figure()
ax = fig.add_subplot(projection='3d')

cmap = ListedColormap(['r', 'g', 'b'])
#ax.scatter(np.log10(dd), pp, si_melt_temp, c=si_melt_temp, cmap=cmap)
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,2]/kappa[0],
           c=result[:,2]/kappa[0], cmap='bwr')
#for i in range(result.shape[0]):
#    ax.plot([np.log10(result[i,0]), np.log10(result[i, 0])],
#            [result[i,1], result[i,1]],
#            c='purple')
ax.plot_surface(xx, yy, fit_func(xx, yy)/kappa[0], alpha=0.3)
ax.set_xlabel('log dwell')
ax.set_ylabel('Current (amps)')
ax.set_zlabel('a.u.')
ax.set_title('Tpeak')
ax.set_zlim(0, 1600)
plt.show()

for i in target:
    t = result[result[:,0]==i]
    plt.plot(t[:,1], t[:,2]/kappa[0])
    plt.plot(t[:,1], fit_func(np.log10(t[:,0]), t[:,1])/kappa[0])
    plt.title(f"{int(i)}mm per sec")
    plt.xlabel
    plt.show()
print(kappa)
