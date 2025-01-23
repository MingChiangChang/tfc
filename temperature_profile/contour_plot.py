import sys
sys.path.insert(0, "../src/")
import glob

from scipy.ndimage import gaussian_filter
import numpy as np
import matplotlib.pyplot as plt

from read_raw import RawReader

plt.rcParams.update({
    # Font settings
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica'],
    'text.usetex': False,  # Use TeX rendering if desired
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'Helvetica',
    'mathtext.it': 'Helvetica:italic',
    'mathtext.bf': 'Helvetica:bold',

    # Figure layout
    'figure.figsize': [9, 4.8],  # Set default figure size (inches)
    'figure.dpi': 300,             # High resolution for publication

    # Axes and labels
    'axes.labelsize': 14,          # Font size for axes labels
    'axes.titlesize': 14,          # Font size for titles
    'axes.linewidth': 0.8,         # Thinner axes lines

    # Tick parameters
    'xtick.labelsize': 12,          # Font size for x-axis tick labels
    'ytick.labelsize': 12,          # Font size for y-axis tick labels
    'xtick.direction': 'in',       # Tick direction
    'ytick.direction': 'in',
    'xtick.major.size': 4,         # Major tick size
    'ytick.major.size': 4,
    'xtick.minor.size': 2,         # Minor tick size
    'ytick.minor.size': 2,
    'xtick.major.width': 0.8,      # Major tick width
    'ytick.major.width': 0.8,
    'xtick.minor.width': 0.6,      # Minor tick width
    'ytick.minor.width': 0.6,

    # Grid
    'grid.alpha': 0.5,             # Transparency of grid
    'grid.linestyle': '--',        # Dashed grid lines
    'grid.linewidth': 0.5,

    # Legend
    'legend.fontsize': 12,          # Font size for legend
    'legend.frameon': False,       # No frame around the legend
    'legend.loc': 'best',

    # Lines and markers
    'lines.linewidth': 1.0,        # Default line width
    'lines.markersize': 4,         # Marker size

    # Savefig options
    'savefig.dpi': 300,            # Save high-resolution figures
    'savefig.format': 'svg',       # Default save format
    'savefig.bbox': 'tight',       # Fit figure tightly to contents
})

xdim = 772
ydim = 1024
kappa = 0.00016339

raw_reader = RawReader(xdim, ydim)
path = "/Volumes/Samsung_T5/1113_data/68mm_per_sec/01297us_057.00w"
bg_path = "/Volumes/Samsung_T5/1113_data/68mm_per_sec/01297us_000.00w"

d = sorted(glob.glob(path + "/Run-0002_Frame-*.raw"))
bg_path = sorted(glob.glob(bg_path + "/Run-0002_Frame-*.raw"))
print(d)
data = raw_reader.load_blue(d[5])
bg_data = raw_reader.load_blue(bg_path[5])

drr = gaussian_filter(((data - bg_data) / bg_data)[200:600, :900] / kappa, 12)
plt.imshow(drr)
x = np.arange(data.shape[1])
y = np.arange(data.shape[0])
xx, yy = np.meshgrid(x, y)
f = plt.contour(drr, levels=[400 + 100*i for i in range(11)])
ax = plt.gca()
ax.clabel(f, fontsize=12, levels= [500, 700, 900, 1100], colors='black', fmt='%1.0f °C')
plt.xticks([])
plt.yticks([])
plt.savefig("contour.pdf")
plt.show()






