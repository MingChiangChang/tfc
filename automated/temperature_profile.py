from pathlib import Path
import sys
sys.path.insert(0, '../src')
import os

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
from tqdm import tqdm

from read_raw import load_blue
from error_funcs import oned_gaussian_func

X_DIM = 1200
Y_DIM = 1920
FRAME_PER_SCAN = 20
x_r = (480, 580)
y_r = (400, 1000)
x_shape = x_r[1]-x_r[0]
y_shape = y_r[1]-y_r[0]
PRED_X_CENTER = 520
INTERVAL = 100

def analyze(dir_path: str, critical_distance: float):
    # Function for each velocity?

    result = []
    velo = get_velocity(os.path.basename(dir_path))

    paths = list(Path(dir_path).glob("*_*"))
    subdir_paths = list(filter(lambda x: not os.path.basename(x).startswith('.'), paths))

    bg = get_avg_background(subdir_paths)
    live = get_live_frames(subdir_paths)
    powers = [get_power(os.path.basename(path)) for path in subdir_paths]
    powers.remove(0.0)

    for power in sorted(powers):
        frame = get_critical_frame(velo, critical_distance)
        dr_r = (live[power][frame] - bg[frame]) / bg[frame]
        #plt.imshow(dr_r, vmin=0., vmax=0.25)
        #plt.show()
        mean, x0, std = single_frame_fitting(dr_r) # Return guassian results
        
        result.append([velo, power, mean, x0, std])
        
    return result

def get_avg_background(paths: list):

    bg_dir = get_bg_dir(paths)

    bg_fn_ls = list(bg_dir.glob("*.raw"))
    bg = np.zeros((len(bg_fn_ls)//FRAME_PER_SCAN, FRAME_PER_SCAN, X_DIM, Y_DIM))
    for bg_fn in tqdm(bg_fn_ls):
        run, frame = parse_raw_fn(os.path.basename(str(bg_fn)))
        bg[run, frame, :, :] = load_blue(bg_fn)
    return np.mean(bg, axis=0)


def get_live_frames(paths: list):
    live_dirs = get_live_dir(paths)
    data_dict = {}
    for live_dir in tqdm(live_dirs):
        power = get_power(os.path.basename(live_dir))
        data_dict[power] = load_data(live_dir)

    return data_dict 


def load_data(dir_path: str):
    img_paths = sorted(list(dir_path.glob("*.raw")))
    imgs = np.zeros((len(img_paths), X_DIM, Y_DIM))

    for idx, path in enumerate(img_paths):
        imgs[idx] = load_blue(path)
   
    return imgs

     

def single_frame_fitting(data):
    t = []
    x = np.arange(y_shape)
    x0 = [0.0, y_shape//2, y_shape//2]
    bounds = ([0., y_shape//2 - 200, 0], [0.3, y_shape//2 + 200, y_shape*3])
    for i in range(INTERVAL):
        err = lambda p: (np.ravel(oned_gaussian_func(*p)(x))
                        - data[PRED_X_CENTER - INTERVAL//2 + i, y_r[0]:y_r[1]])
        pfit = least_squares(err, x0, bounds=bounds)
        t.append(pfit.x)
    t = np.array(t)

    x = np.arange(INTERVAL)
    err = lambda p: np.ravel(oned_gaussian_func(*p)(x)) - t[:,0]
    pfit = least_squares(err, [0.0, 40., 50.], bounds=([0., 30., 0.], [0.5, 50., 150.]))
    peak_loc = int( np.round(PRED_X_CENTER - INTERVAL//2 + pfit.x[1]))

    x = np.arange(y_shape)
    plt.plot(data[peak_loc, y_r[0]:y_r[1]])
    plt.show()
    err = lambda p: np.ravel(oned_gaussian_func(*p)(x)) - data[peak_loc, y_r[0]:y_r[1]]
    pfit = least_squares(err, x0, bounds=bounds)
    return pfit.x


def get_critical_frame(velo, critical_distance):
    FPS = 40
    frame = np.round(critical_distance / velo * FPS)
    if frame <= 19:
        return int(frame)
    else:
        return 19 

def parse_raw_fn(fn: str):
    """
    Run-0004_Frame-0021.raw -> 4, 21
    """
    
    fn = fn.split('.')[0] 
    run, frame = fn.split('_')
    run = int(run.split('-')[1])
    frame = int(frame.split('-')[1])
    return run, frame
     
def get_bg_dir(paths: list):
    power = [get_power(os.path.basename(paths[i])) for i in range(len(paths))
                                       if not os.path.basename(paths[i]).startswith('.')]
    return paths[power.index(0.0)]

def get_live_dir(paths: list):
    power = [get_power(os.path.basename(paths[i])) for i in range(len(paths))
                                       if not os.path.basename(paths[i]).startswith('.')]
    return (np.array(paths)[np.array(power) > 0]).tolist() # not the best but easy implementation


def get_power(dir_name: str):
    """
    30120us_050.00W => 50
    """
    p = str(dir_name).split("_")[1]
    return float(p[:p.index("W")])

def get_velocity(dir_name: str):
    """
    x=5_50mm_per_sec => 50
    """
    v = dir_name.split("_")[1]
    return float(v[:v.index('m')])


if __name__ == "__main__":
    home = Path.home()
    
    path = home / "Desktop" / "Code" / "tfc" / "automated" / "diode"
    
    #bg = get_avg_background(list((path / "x=0_10mm_per_sec").glob("*")))
    #live = get_live_frames(list((path / "x=0_10mm_per_sec").glob("*")))
    result = [] 
    for p in path.glob("*"):
        if not os.path.basename(p).startswith('.'):
            result.append(analyze(p, 5.))
    r = [result[i][j] for i in range(len(result)) for j in range(len(result[i]))]
    #np.save("fit.npy", np.array(r))
