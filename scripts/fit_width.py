import sys
sys.path.insert(0, '../src')

import json
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.colors import ListedColormap
from error_funcs import twod_plane
from temp_calibration import fit_xy_to_z_surface_with_func


with open("/Users/ming/Desktop/width_fit.json", 'r') as f:
    data = json.load(f)

widths = []
for velo in data:
    for pw in data[velo]:
        t = np.array(data[velo][pw])
        widths.append([velo, pw, np.mean(t[:,2]), np.std(t[:,2]), np.mean(t[:,3]), np.std(t[:,3])])

result = np.array(widths).astype(float)
x = np.linspace(np.log10(9), np.log10(380), 20)
y = np.linspace(30, 65, 20)
xx, yy = np.meshgrid(x, y)


pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(result[:,0]),
                                      result[:,1], result[:,2],
                                      twod_plane, [1., 1., 1.])
print(pfit)
fit_func = twod_plane(*pfit)

######################## Plotting ###################################3
fig = plt.figure()
ax = fig.add_subplot(projection='3d')
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,2],
           c=result[:,2], cmap='bwr')
#for i in range(result.shape[0]):
#    ax.plot([np.log10(result[i,0]), np.log10(result[i, 0])],
#            [result[i,1], result[i,1]],
#            c='purple')
ax.plot_surface(xx, yy, fit_func(xx, yy), alpha=0.5)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('left width')
ax.set_title('left width')
ax.set_zlim(0, 300)
plt.show()


fig = plt.figure()
ax = fig.add_subplot(projection='3d')
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,3],
           c=result[:,3], cmap='bwr')
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('left width std')
plt.show()

pfit, _, _ = fit_xy_to_z_surface_with_func(np.log10(result[:,0]),
                                      result[:,1], result[:,4],
                                      twod_plane, [1., 1., 1.])
print(pfit)
fit_func = twod_plane(*pfit)
fig = plt.figure()
ax = fig.add_subplot(projection='3d')
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,4],
           c=result[:,4], cmap='bwr')

ax.plot_surface(xx, yy, fit_func(xx, yy), alpha=0.5)
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('right width')
ax.set_title('right width')
ax.set_zlim(0, 300)
plt.show()


fig = plt.figure()
ax = fig.add_subplot(projection='3d')
cmap = ListedColormap(['r', 'g', 'b'])
ax.scatter(np.log10(result[:,0]), result[:,1], result[:,5],
           c=result[:, 5], cmap='bwr')
ax.set_xlabel('log velocity')
ax.set_ylabel('Power (W)')
ax.set_zlabel('right width std')
ax.set_title('Tpeak')
plt.show()
