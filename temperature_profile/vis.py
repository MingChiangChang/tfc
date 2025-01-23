import os
import sys
sys.path.insert(1, '/Users/ming/Desktop/Code/tfc/src')
import glob

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares

from read_raw import load_blue
from error_funcs import two_lorentz

velo = 45 

# bg_path = "/Users/ming/Library/CloudStorage/Box-Box/MURI-SARA/Ambient Control/New folder (2)/0A*.raw"
# path = "/Users/ming/Library/CloudStorage/Box-Box/MURI-SARA/Ambient Control/New folder (2)/73A*.raw"
path = f"{velo}mm_per_sec/{str(88200//velo).zfill(5)}us_049.00W"
bg_path = f"{velo}mm_per_sec/{str(88200//velo).zfill(5)}us_000.00W"
print(path)
raw_ls = sorted(glob.glob(f"{path}/*.raw"))
bg_ls = sorted(glob.glob(f"{bg_path}/*.raw"))

for bg, raw in zip(bg_ls, raw_ls) :
    b = load_blue(bg)
    d = load_blue(raw)
    m = np.max(d)

    plt.imshow(b, vmax=m)
    plt.axis('off')
    plt.show()

    plt.imshow(d, vmax=m)
    plt.axis('off')
    plt.show()

    plt.imshow((d-b)/b)
    plt.axis('off')
    # plt.title(os.path.basename(raw))
    plt.show()

    for i in range(350,450,20):
        data = ((d-b)/b)[i, :]
        
        x = np.arange(data.shape[0])
        err = lambda p: np.ravel(two_lorentz(*p)(x)) - data

        # FF
        x0 = [0.15, 600., 200., 200.]
        bounds = ([0., 400., 100., 100.], [0.5, 800., 600., 500.])

        pfit = least_squares(err, x0, bounds=bounds)
        plt.scatter(x[::20], ((d-b)/b)[i, ::20], marker='o')
        plt.plot(x, two_lorentz(*pfit.x)(x))
        plt.xlabel("Pixel")
        plt.ylabel("ΔR/R")
    plt.show()

