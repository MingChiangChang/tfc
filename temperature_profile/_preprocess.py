import sys
sys.path.insert(1, '../')
sys.path.insert(1, '/Users/ming/Desktop/Code/tfc/src')
from pathlib import Path
import json

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from TR_analyzer import Stripe_TR_analyzer, Single_TR_analyzer
from configure_1113 import Configs
from read_raw import load_blue


config = Configs() # global lol

def main():

    x = 0.
    y = 0.

    for velo, dwell in zip(config.VELOCITY, config.DWELL):

        path = Path(f"/Users/ming/Desktop/Code/tfc")
        path = path /  "temperature_profile" / f"{velo}mm_per_sec"

        bg_path = path / f"{str(dwell).zfill(5)}us_000.00W"
        bg = load_raws_in_dir(bg_path)
        bg = np.mean(bg, axis=0) 
        frame = config.FRAME[velo]
        
        for power in tqdm(sorted(config.POWER[velo]), desc=f'{dwell}us'):
            print(power)
            
            dir_path = path / f"{str(dwell).zfill(5)}us_{power:06.2f}W" 
            print(str(dir_path))
            raw = load_raws_in_dir(dir_path)
            print("Finish loading..")
            print(raw.shape)

            analyzer = Stripe_TR_analyzer(x, y, velo, power, raw, bg)
            analyzer.analyze(x_min = config.X_MIN, x_max = config.X_MAX,
                                          y_min = config.Y_MIN, y_max = config.Y_MAX)
            analyzer.save_json(fn = analyzer.condition_str + f'.json')
            analyzer.plot_dr_r(save=True)# , fn=f"{analyzer.condition_str}_dr_r.png")
            analyzer.plot_center_pos(save=True)#, fn=f"{analyzer.condition_str}_center_pos.png")
            analyzer.plot_sigma(save=True)

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
            
            
        
def load_raws_in_dir(dir_path):

    files = np.array(sorted(dir_path.glob("*.raw")))
    files = files.reshape((-1, config.NFRAMES))
    data = np.zeros((*files.shape, config.X_DIM, config.Y_DIM))

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            data[i, j] = load_blue(files[i, j])

    return data



if __name__ == "__main__":
    main()

