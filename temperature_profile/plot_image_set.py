import sys
sys.path.insert(0, '/Users/ming/Desktop/Code/tfc/src')

import matplotlib.pyplot as plt
import numpy as np
import matplotlib as mpl

from read_raw import load_blue


plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica'],
    'text.usetex': False,  # Use TeX rendering if desired
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'Helvetica',
    'mathtext.it': 'Helvetica:italic',
    'mathtext.bf': 'Helvetica:bold',
    'figure.figsize': [12.8, 9.6],  # Set default figure size (inches)
    'savefig.dpi': 300,            # Save high-resolution figures
    'savefig.format': 'svg',       # Default save format
    'savefig.bbox': 'tight',       # Fit figure tightly to contents
    'axes.titlesize': 12,
})

mpl.rcParams['axes.spines.right'] = False
mpl.rcParams['axes.spines.top'] = False
mpl.rcParams['axes.spines.bottom'] = False
mpl.rcParams['axes.spines.left'] = False

live = load_blue("/Volumes/Samsung_T5/1113_data/68mm_per_sec/01297us_057.00W/Run-0000_Frame-0009.raw")
bg = load_blue("/Volumes/Samsung_T5/1113_data/68mm_per_sec/01297us_000.00W/Run-0000_Frame-0009.raw")
live = live[:,:-100]
bg = bg[:,:-100]

fig, ax = plt.subplots(1, 3)
vmax = np.max(live)
ax[0].imshow(bg, vmin = 0, vmax = vmax)
ax[0].set_xticks([])
ax[0].set_yticks([])
ax[0].set_title("Backgound Image")
ax[1].imshow(live, vmin = 0, vmax = vmax)
ax[1].set_xticks([])
ax[1].set_yticks([])
ax[1].set_title("Live Image")
ax[2].imshow((live - bg ) /bg, vmin = 0,)
ax[2].set_xticks([])
ax[2].set_yticks([])
ax[2].set_title("ΔR/R")

plt.savefig("image_set.svg")
plt.show()
