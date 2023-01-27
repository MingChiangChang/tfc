import sys
import os
sys.path.insert(0, "../src/")
import glob

import matplotlib.pyplot as plt
from tqdm import tqdm

from read_raw import load_blue

path = "/Users/ming/Desktop/Code/tfc/automated/diode"

for d in glob.glob(path + "/*"):
    print(d)
    for g in tqdm(glob.glob(d + "/*"), desc=f"{os.path.basename(d)}"):
        print(g)
        for i in glob.glob(g + "/*.raw"):
            plt.imshow(load_blue(i))
            plt.savefig("figure/" + os.path.basename(d) + '_' + os.path.basename(g) + '_' + os.path.basename(i)[:-4] + ".png")

