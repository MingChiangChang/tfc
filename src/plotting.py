from pathlib import Path
import os
import json
import matplotlib.pyplot as plt
import numpy as np

def sort_current(current_ls: list):
    current = [int(c[:-1]) for c in current_ls]
    current, current_ls = zip(*sorted(zip(current, current_ls)))
    return current_ls

kappa = 1.4*10**-4
home = Path.home()

#forbidden = {"15"}

path = home / "Desktop" / "TR"
for j in path.glob("*.json"):
    with open(j, "r") as f:
        data = json.load(f)

    current_ls = list(data)
    current_ls = sort_current(current_ls)
    print(current_ls)
    for current in current_ls:
        t = np.array(data[current])
        plt.plot(np.arange(t.shape[0]), t[:,0]/kappa, marker='o', label=current)

    plt.legend()
    plt.title(os.path.basename(j)[:-5])
    plt.ylim(0, 1600)
    plt.show()


