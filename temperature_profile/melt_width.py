import sys
sys.path.insert(0, "..//src")

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import leastsq

from temp_profile_2025 import left_right_width, temp_surface_func, LaserPowerMing_Spring2025
from error_funcs import two_lorentz


def exponential_fit(e, a):
    return lambda x: a*(x)**e #+ b*(x-y_th)

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
    'figure.figsize': [6.4, 4.8],  # Set default figure size (inches)
    'figure.dpi': 300,             # High resolution for publication

    # Axes and labels
    'axes.labelsize': 14,          # Font size for axes labels
    'axes.titlesize': 12,          # Font size for titles
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
    'legend.fontsize': 10,          # Font size for legend
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

# Kappa using gold
params = {
        9: [2.36105623e+00, 2.35196170e-05, 0.00012912], 
       13: [2.47776076e+00, 1.48375365e-05, 0.00012905],
       20: [2.56027806e+00, 1.02235989e-05, 0.00013300],
       30: [2.64846875e+00, 6.76589306e-06, 0.00013465],
       45: [2.76562452e+00, 3.89975677e-06, 0.00012865],
       68: [2.76890593e+00, 3.30149767e-06, 0.00013282],
      103: [2.98186331e+00, 1.19993420e-06, 0.00012814],
      155: [3.06725636e+00, 6.79160171e-07, 0.00012831],
      #234: [3.28541504e+00, 2.16221615e-07, 0.00017006],
      #352: [3.42531862e+00, 9.04559995e-08, 0.00016183],
      }
# Kappa using Silicon
# params = {
#         9: [2.36105623e+00, 2.35196170e-05, 0.00015388], 
#        13: [2.47776076e+00, 1.48375365e-05, 0.0001636],
#        20: [2.56027806e+00, 1.02235989e-05, 0.00015667],
#        30: [2.64846875e+00, 6.76589306e-06, 0.00015596],
#        45: [2.76562452e+00, 3.89975677e-06, 0.00015754],
#        68: [2.76890593e+00, 3.30149767e-06, 0.00015608],
#       103: [2.98186331e+00, 1.19993420e-06, 0.00016285],
#       155: [3.06725636e+00, 6.79160171e-07, 0.00015952],
#       234: [3.28541504e+00, 2.16221615e-07, 0.00017006],
#       352: [3.42531862e+00, 9.04559995e-08, 0.00016183],
#         }
# Use fit for each velocity instead
# p_func = temp_surface_func(*[-0.01824834, 0.05924233, -0.01709909, 0.01145558, 2.74505353])
# p_func = temp_surface_func(*[-0.01345785, 0.04789666, -0.06934948, 0.17289481, 2.65508528])
# melt_data = np.genfromtxt("data.csv", delimiter=',')
melt_data = np.genfromtxt("gold_data.csv", delimiter=',', skip_header=1)
velos = np.unique(melt_data[:,0])

tau = 10000 # 10ms
melting_point = 1047 #1414# 1047
PXL_SIZE = 0.9813

ks = []

for tau in np.linspace(np.log10(250), np.log10(10000), 10):
    v = np.round(88200/10**tau)
    v = velos[np.argsort(np.abs(velos - v))[0]]
    mask = melt_data[:,0] == v
    m = melt_data[mask, :]

    flag = 0
    d = []

    def err(p):
        d = []
        powers = m[:,1]
        for power in powers:
            temp = exponential_fit(*params[v][:2])(power) / p
            lw, rw = left_right_width(10**tau, temp) 
            t_func = two_lorentz(temp, 0, lw*PXL_SIZE, rw*PXL_SIZE)
            
            x = np.linspace(-1000, 1000, 2000)
            d.append(np.sum((t_func(x)) > melting_point))
        d = np.array(d)
        return d - m[:,2]
    kappa, cov_x, infodict, mesg, ier = leastsq(
            err, [0.00013],epsfcn=5.0, full_output=True
            ) # Need to increase `epsfcn` to make initial step larger
    print(kappa)
    ks.append(kappa)
    kappa = 0.00013


    for power in [np.max(m[:,1])-0.3*i for i in range(10)][::-1]:#[1400 + 10*i for i in range(30)]:
        # temp = p_func(np.log10(88200 / 10**tau), power)
        # temp = exponential_fit(*params[v][:2])(power) / kappa #params[v][-1]
        temp = exponential_fit(*params[v][:2])(power) / kappa #params[v][-1]
        print(temp)
        # ower = LaserPowerMing_Spring2025(10**tau, temp)
        lw, rw = left_right_width(10**tau, temp)
        t_func = two_lorentz(temp, 0, lw, rw)
        
        x = np.linspace(-500, 500, 1000)
        print(t_func(x))
        plt.plot(x, t_func(x) * kappa, label=f"{power:.1f}W")
    plt.legend()
    plt.xlabel("Relative Position (μm)")
    plt.ylabel("ΔR/R")
    # if v == 68:
    #     plt.savefig("drr_vs_power.pdf")
    plt.show()
    

