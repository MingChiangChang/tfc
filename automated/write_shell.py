"""Script for writing ThermalReflectance shell commands"""

import numpy as np

BEAM_WIDTH = 88200.
BG_REP = 5


def write_commands(f, repeat, power_ls, velocity, x_pos, y_min, y_max, pre, ring_size=30):
    dwell = np.round(BEAM_WIDTH / velocity, 2)
    one_line_commands(f, BG_REP, 0., dwell, x_pos, y_min, y_max, pre, ring_size)
    for power in power_ls:
        one_line_commands(f, repeat, power, dwell, x_pos, y_min, y_max, pre, ring_size)

def one_line_commands(f, repeat, power, dwell, x_pos, y_min, y_max, pre, ring_size): 
    f.write("python ThermalReflectance.py ")
    f.write(f"-n {repeat} ")
    f.write(f"-p {power} ")
    f.write(f"-d {dwell} ")
    f.write(f"-pmin {x_pos} {y_min} ")
    f.write(f"-pmax {x_pos} {y_max} ")
    f.write(f"-r {ring_size} ")
    f.write(f"-pre {pre}")
    f.write("\n")
    


if __name__ == "__main__":
    shell_name = "test.sh"
    speeds = [9., 13., 20., 30., 45., 68., 103., 155., 190., 234., 352.]
    x = 0
    with open(shell_name, 'w') as f:
        for speed in speeds[::-1]:
            if speed > 25: 
                write_commands(f, 5, [10. + 5*i for i in range(10)],
                           speed, x_pos=x, y_min=0, y_max=12,
                           pre=f"{int(speed)}mm_per_sec",
                           ring_size=60) 
            else:
                write_commands(f, 5, [10. + 5*i for i in range(10)],
                           speed, x_pos=x, y_min=0, y_max=np.round(speed*0.58, 2),
                           pre=f"{int(speed)}mm_per_sec",
                           ring_size=60)

        x += 2
