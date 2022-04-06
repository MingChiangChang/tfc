from pathlib import Path
import os
import json
import matplotlib.pyplot as plt
import numpy as np

from util import sort_current

FPS = 40.
kappa = 1.2*10**-4
home = Path.home()

#rng = {15.: 30, 35.: 30,  75.: 30, 150.: 15, 300.: 8, 55.: 30}

path = home / "Desktop" / "TR" / "co2"
for j in path.glob("*test.json"):
    with open(j, "r") as f:
        data = json.load(f)
    velo_str = os.path.basename(j)
    velo = float(velo_str[:velo_str.index("mm per")])
    current_ls = list(data)
    _, current_ls = sort_current(current_ls)
    plt.figure(figsize=(10,6), dpi=150)
    for current in current_ls:
        t = np.array(data[current])
        #plt.plot(np.arange(rng[velo])*velo/FPS,
        #         t[:rng[velo],0]/kappa, marker='o', label=current)
        plt.plot((np.arange(t.shape[0])-1)*velo/FPS,
                t[:,0]/kappa, marker='o', label=current)


    plt.legend(loc=6)
    plt.title(os.path.basename(j)[:-5])
    plt.ylim(0, 1600)
    plt.xlabel("distance into the stripe (mm)")
    plt.ylabel("Projected temperature (C)")
    plt.savefig(velo_str[:-5] + "_temp.png")
    plt.clf()
    plt.close("all")
    
    for current in current_ls[3:]:
        t = np.array(data[current])
        #plt.plot(np.arange(rng[velo])*velo/FPS,
        #         t[:rng[velo],0]/kappa, marker='o', label=current)
        plt.plot((np.arange(t.shape[0])-1)*velo/FPS,
                t[:,1], marker='o', label=current)


    plt.legend(loc=6)
    plt.title(os.path.basename(j)[:-5])
    plt.ylim(400, 1000)
    plt.xlabel("distance into the stripe (mm)")
    plt.ylabel("Center position (pxl)")
    plt.savefig(velo_str[:-5] + "_xpos.png")
    plt.clf()
    plt.close("all")

    for current in current_ls[3:]:
        t = np.array(data[current])
        #plt.plot(np.arange(rng[velo])*velo/FPS,
        #         t[:rng[velo],0]/kappa, marker='o', label=current)
        plt.plot((np.arange(t.shape[0])-1)*velo/FPS,
                t[:, 2]-t[:,3], marker='o', label=current)


    plt.legend(loc=6)
    plt.title(os.path.basename(j)[:-5])
    plt.ylim(0, 300)
    plt.xlabel("distance into the stripe (mm)")
    plt.ylabel("Difference in width of 2 lorentz")
    plt.savefig(velo_str[:-5] + "_diff.png")
    plt.clf()
    plt.close("all")
