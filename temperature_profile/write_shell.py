"""Script for writing ThermalReflectance shell commands"""

import numpy as np

from configure_1113 import Configs

BEAM_WIDTH = 88200.
BG_REP = 5

config = Configs()


def write_commands(f, repeat, power_ls, velocity,
                   x_pos, y_min, y_max, pre, frame, ring_size=60):
    dwell = np.round(BEAM_WIDTH / velocity, 2)
    write_one_line_commands(f, BG_REP, 0., dwell, x_pos, y_min, y_max, pre, frame, ring_size)
    for power in power_ls:
        write_one_line_commands(f, repeat, power, dwell, x_pos, y_min, y_max, pre, frame, ring_size)

def write_one_line_commands(f, repeat, power, dwell, x_pos, y_min, y_max, pre, frame, ring_size): 
    f.write("python ThermalReflectance.py ")
    f.write(f"-n {repeat} ")
    f.write(f"-p {power} ")
    f.write(f"-d {dwell} ")
    f.write(f"-pmin {x_pos} {y_min} ")
    f.write(f"-pmax {x_pos} {y_max} ")
    f.write(f"-f {frame} ")
    f.write(f"-r {ring_size} ")
    f.write(f"-pre {pre}")
    f.write("\n")
    


if __name__ == "__main__":
    # shell_name = "run.sh"
    shell_name = "run_1113_extra.sh"
    # speeds = [9., 13., 20., 30., 45., 68., 103., 155., 190., 234., 352.]

    # Try to reuse the center
    x = -1 
    with open(shell_name, 'w') as f:
        for v in sorted(config.POWER, reverse=True):
            write_commands(f, 5, config.POWER[v],
                       v, x_pos=x, y_min=0, y_max=10,
                       pre=f"{int(v)}mm_per_sec",
                       frame=config.N_FRAMES[v],
                       ring_size=config.N_FRAMES[v],
                       ) 
