import numpy as np
import matplotlib.pyplot as plt

d_new = np.genfromtxt("2024.11.4_points.csv",
                      skip_header=1,
                      delimiter=",")



d_old = np.genfromtxt("/Users/ming/Library/CloudStorage/Box-Box/MURI-SARA/CHESS/2024-Winter_CHESS_run/TemperatureCal/2024.10.6_points.csv",
                      skip_header=1,
                      delimiter=",")

d_new = d_new[:,:3]
d_old = d_old[:,:3]

ax = plt.figure().add_subplot(projection="3d")
ax.scatter(d_new[:,0], d_new[:,1],
           d_new[:,2] / np.mean(d_new[:,2]))
ax.scatter(d_old[:,0], d_old[:,1], d_old[:,2] / np.mean(d_old[:,2]))



plt.show()

