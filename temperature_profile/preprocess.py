import sys
sys.path.insert(1, '../')
sys.path.insert(1, '/Users/ming/Desktop/Code/tfc/src')
from pathlib import Path
import json

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from TR_analyzer import Single_TR_analyzer
from configure_0802 import Configs
from read_raw import load_blue


config = Configs() # global lol

def main():

    for velo, dwell in zip(config.VELOCITY, config.DWELL):
        # path = Path(f"/Users/ming/Desktop/CHESS_2023_spring/{velo}mm_per_sec")
        path = Path(f'{velo}mm_per_sec')

        frame = config.FRAME[velo]

        bg_path = path / f"{str(dwell).zfill(5)}us_000.00W"
        bg = load_raws_in_dir(bg_path, config.N_FRAMES[velo])
        bg = np.mean(bg, axis=0) 
        
        for power in tqdm(config.POWER[velo], desc=f"velo={velo}"):
            dir_path = path / f"{str(dwell).zfill(5)}us_{power:06.2f}W" 
            raw = load_raws_in_dir(dir_path, config.N_FRAMES[velo])

            for i in range(raw.shape[0]):
                # print(velo, power, i, frame)
                # print(raw.shape)
                # print(bg.shape)
                analyzer = Single_TR_analyzer(0, 0, velo, power, raw[i, frame], bg[frame])
                analyzer.analyze_single_frame(x_min = config.X_MIN, x_max = config.X_MAX,
                                              y_min = config.Y_MIN, y_max = config.Y_MAX)
                analyzer.save_json(fn = analyzer.condition_str + f'_run_{i}.json')
                analyzer.plot(save=True, fn=f"{analyzer.condition_str}_run_{i}.png")

            js = []
            for i in range(raw.shape[0]):
                with open(analyzer.condition_str + f'_run_{i}.json', 'r') as f:
                    js.append(json.load(f)) 

                collected_data = {}
                lorentz_peaks = [j['lorentz_peak'] for j in js]
                lorentz_left_widths = [j['lorentz_left_width'] for j in js]
                lorentz_right_widths = [j['lorentz_right_width'] for j in js]
                lorentz_peak_indicies = [j['lorentz_peak_idx'] for j in js]
                gauss_peaks = [j['gauss_peak'] for j in js]
                gauss_left_widths = [j['gauss_left_width'] for j in js]
                gauss_right_widths = [j['gauss_right_width'] for j in js]
                gauss_peak_indicies = [j['gauss_peak_idx'] for j in js]

                collected_data['lorentz_peaks'] = lorentz_peaks 
                collected_data['lorentz_left_widths'] = lorentz_left_widths 
                collected_data['lorentz_right_widths'] = lorentz_right_widths 
                collected_data['lorentz_peak_indicies'] = lorentz_peak_indicies
                collected_data['lorentz_peak_mean'] = np.mean(lorentz_peaks)
                collected_data['lorentz_peak_std'] = np.std(lorentz_peaks)
                collected_data['lorentz_left_width_mean'] = np.mean(lorentz_left_widths)
                collected_data['lorentz_left_width_std'] = np.std(lorentz_left_widths)
                collected_data['lorentz_right_width_mean'] = np.mean(lorentz_right_widths)
                collected_data['lorentz_right_width_std'] = np.std(lorentz_left_widths)

                collected_data['gauss_peaks'] = gauss_peaks
                collected_data['gauss_left_widths'] = gauss_left_widths
                collected_data['gauss_right_widths'] = gauss_right_widths
                collected_data['gauss_peak_indicies'] = gauss_peak_indicies
                collected_data['gauss_peak_mean'] = np.mean(gauss_peaks)
                collected_data['gauss_peak_std'] = np.std(gauss_peaks)
                collected_data['gauss_left_width_mean'] = np.mean(gauss_left_widths)
                collected_data['gauss_left_width_std'] = np.std(gauss_left_widths)
                collected_data['gauss_right_width_mean'] = np.mean(gauss_right_widths)
                collected_data['gauss_right_width_std'] = np.std(gauss_left_widths)

                with open(analyzer.condition_str + '.json', 'w') as f:
                    json.dump(collected_data, f)
            
            
        
def load_raws_in_dir(dir_path, n_frames = 30):

    files = np.array(sorted(dir_path.glob("*.raw")))
    files = files.reshape((-1, n_frames))
    data = np.zeros((*files.shape, config.X_DIM, config.Y_DIM))

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            data[i, j] = load_blue(files[i, j])

    return data







if __name__ == "__main__":
    main()

