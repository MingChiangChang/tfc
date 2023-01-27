"""Script for writing ThermalReflectance shell commands"""
BEAM_WIDTH = 88200.
BG_REP = 5


def write_commands(f, repeat, power_ls, velocity, x_pos, y_min, y_max, pre, ring_size=30):
    dwell = BEAM_WIDTH / velocity
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
    with open(shell_name, 'w') as f:
        write_commands(f, 1, [10. + 5*i for i in range(10)],
                          100, x_pos=0, y_min=-8, y_max=8, pre="test", ring_size=30) 

