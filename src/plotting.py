from pathlib import Path
import os
import json
import matplotlib.pyplot as plt
import numpy as np

from util import sort_current

FPS = 40.
kappa = 1.4*10**-4
home = Path.home()

rng = {15.: 30, 35.: 30,  75.: 30, 150.: 15, 300.: 8, 55.: 30}

path = home / "Desktop" / "TR"
for j in path.glob("*.json"):
    with open(j, "r") as f:
        data = json.load(f)
    velo_str = os.path.basename(j)
    velo = float(velo_str[:velo_str.index("mm per")])
    current_ls = list(data)
    _, current_ls = sort_current(current_ls)
    plt.figure(figsize=(10,6), dpi=150)
    for current in current_ls:
        t = np.array(data[current])
        plt.plot(np.arange(rng[velo])*velo/FPS,
                 t[:rng[velo],0]/kappa, marker='o', label=current)

    plt.legend(loc=6)
    plt.title(os.path.basename(j)[:-5])
    plt.ylim(0, 1600)
    plt.xlabel("distance into the stripe (mm)")
    plt.ylabel("Ratio to max temperature")
    plt.savefig(velo_str[:-5] + "_2.png")


