import sys
sys.path.insert(1, '../')
sys.path.insert(1, '/Users/ming/Desktop/Code/tfc/src')
from pathlib import Path
import json

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from matplotlib.collections import PolyCollection
from matplotlib import colors as mcolors

from TR_analyzer import Stripe_TR_analyzer, Single_TR_analyzer
from configure_1113 import Configs
from read_raw import load_blue, RawReader
from error_funcs import two_lorentz, oned_gaussian_func

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

config = Configs() # global lol
x_min = config.X_MIN + 25
x_max = config.X_MAX - 35
y_min = config.Y_MIN
y_max = config.Y_MAX
prop_cycle = plt.rcParams['axes.prop_cycle']
colors = prop_cycle.by_key()['color']
interval = 8
z_min = 0.05
z_max = 0.2

def cc(arg):
    return mcolors.to_rgba(arg, alpha=0.2)

def main():

    x = 0.
    y = 0.

    raw_reader = RawReader(config.X_DIM, config.Y_DIM)

    # for velo, dwell in zip(config.VELOCITY, config.DWELL):
    for velo, dwell in zip([68], [1297]):

        path = Path("/Volumes/Samsung_T5/1113_data/")
        path = path / f"{velo}mm_per_sec"

        bg_path = path / f"{str(dwell).zfill(5)}us_000.00W"
        bg = load_raws_in_dir(raw_reader, bg_path)
        bg = np.mean(bg, axis=0) 
        frame = config.FRAME[velo]
        
        for power in tqdm(sorted(config.POWER[velo], reverse=True), desc=f'{dwell}us'):
            dir_path = path / f"{str(dwell).zfill(5)}us_{power:06.2f}W" 
            raw = load_raws_in_dir(raw_reader, dir_path)[2, frame, :, :]

            analyzer = Single_TR_analyzer(x, y, velo, power, raw, bg[frame])
            analyzer.analyze_single_frame(x_min = x_min, x_max = x_max,
                                          y_min = y_min, y_max = y_max)
            print(analyzer.fit_results.shape)

            fig = plt.figure()
            ax = fig.add_subplot(projection='3d')
            print(np.linspace(x_min, x_max-1, 10))
            for color_i, i in enumerate(np.linspace(x_min, x_max-1, 10)):
                y = np.arange(y_min, y_max, interval)
                x = np.repeat(i, len(y))
                ind = int(i-x_min)
                r = analyzer.reflectance[int(i), y_min:y_max:interval]
                r_mask = r > z_min
                x = x[r_mask]
                y = y[r_mask]
                r = r[r_mask]

                fit_y = np.arange(0, y_max-y_min)
                zfit = analyzer.fit_results[ind][0] + two_lorentz(*analyzer.fit_results[ind][1:])(fit_y)
                mask = zfit > z_min
                fit_y = fit_y[mask] + y_min
                zfit = zfit[mask]
                fit_x = np.repeat(i, len(fit_y))
            
                ax.scatter(x, y, r, label=str(int(i)), s=2, color=colors[color_i], alpha=0.6, edgecolors='none')
                ax.plot(fit_x, fit_y, zfit, color=colors[color_i])
                verts = list(zip(fit_y, zfit))
                poly = PolyCollection([verts], facecolors=[cc(colors[color_i])])
                ax.add_collection3d(poly, zs=[i], zdir='x')

                ax.scatter([i], analyzer.fit_results[ind, 2:3]+y_min,
                           analyzer.fit_results[ind, 0:1] + analyzer.fit_results[ind, 1:2],
                           marker='D', s=50, color=colors[color_i], edgecolors='gray')

                ax.scatter([i], y_min, analyzer.fit_results[ind, 0:1] + analyzer.fit_results[ind, 1:2],
                           marker='D', s=50, color=colors[color_i], alpha=0.2)
            # plt.legend()
            # ax.grid(alpha=0.2, linestyle='-', linewidth=2)
            ax.set_xlabel("X Position (pxl)")
            ax.set_ylabel("Y Position (pxl)")
            ax.set_zlabel("ΔR/R", rotation=90.)
            ax.set_zlim(z_min, z_max)
            ax.invert_yaxis()
            ax.view_init(elev=28., azim=-103)
            # plt.savefig("horizontal_fit.svg")
            plt.show()
            
            plt.scatter(np.arange(x_min, x_max),
                        analyzer.fit_results[:,0] + analyzer.fit_results[:,1], marker='D',
                        edgecolors='gray', s=30, linewidth=0.75, label="Peak ΔR/R")
            plt.plot(np.arange(x_min, x_max),
                     (analyzer.peak_int_fit_result[0] 
                      + two_lorentz(*analyzer.peak_int_fit_result[1:])(np.arange(0, x_max-x_min))),
                     label='Two-Lorentzian Fit', linestyle=':')
            plt.scatter([x_min + analyzer.peak_int_fit_result[2]],
                        [analyzer.peak_int_fit_result[0] + analyzer.peak_int_fit_result[1]],
                        marker='*', s=250, edgecolors='black',linewidth=0.5, color='r', zorder=3, label="Maximum")
            plt.legend()
            plt.xlabel("X Position (pxl)")
            plt.ylabel("ΔR/R")
            plt.savefig("maximum_fitting.svg")
            plt.show()


            # analyzer.plot()


            # analyzer = Stripe_TR_analyzer(x, y, velo, power, raw, bg)
            # analyzer.analyze(x_min = config.X_MIN, x_max = config.X_MAX,
            #                               y_min = config.Y_MIN, y_max = config.Y_MAX)
            # analyzer.save_json(fn = analyzer.condition_str + f'.json')
            # analyzer.plot_dr_r(save=True)# , fn=f"{analyzer.condition_str}_dr_r.png")
            # analyzer.plot_center_pos(save=True)#, fn=f"{analyzer.condition_str}_center_pos.png")
            # analyzer.plot_sigma(save=True)

            # js = []
            # for i in range(raw.shape[0]):
            #     # with open(analyzer.condition_str + f'_run_{i}.json', 'r') as f:
            #     #     js.append(json.load(f)) 

            #     collected_data = {}
            #     peaks = [j['peak'] for j in js]
            #     left_widths = [j['left_width'] for j in js]
            #     right_widths = [j['right_width'] for j in js]
            #     collected_data['peaks'] = peaks 
            #     collected_data['left_widths'] = left_widths 
            #     collected_data['right_widths'] = right_widths 
            #     collected_data['peak_mean'] = np.mean(peaks)
            #     collected_data['peak_std'] = np.std(peaks)
            #     collected_data['left_width_mean'] = np.mean(left_widths)
            #     collected_data['left_width_std'] = np.std(left_widths)
            #     collected_data['right_width_mean'] = np.mean(right_widths)
            #     collected_data['right_width_std'] = np.std(left_widths)

            #     with open(analyzer.condition_str + '.json', 'w') as f:
            #         json.dump(collected_data, f)
            
            
        
def load_raws_in_dir(raw_reader, dir_path):

    files = np.array(sorted(dir_path.glob("Run*.raw")))
    files = files.reshape((-1, config.NFRAMES))
    data = np.zeros((*files.shape, config.X_DIM, config.Y_DIM))

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            data[i, j] = raw_reader.load_blue(files[i, j])

    return data



if __name__ == "__main__":
    main()

