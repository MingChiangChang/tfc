import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

fit = np.load("fit.npy")
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')


ax.scatter(fit[:,0], fit[:,1], zs=fit[:,2])
plt.show()
