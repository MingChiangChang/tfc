from pathlib import Path
import os

from tqdm import tqdm
import matplotlib.pyplot as plt

from read_raw import load_blue

home = Path.home() 
path = home / "Desktop" / "TR" / "co2"
dir_paths = path.glob("353mm per sec")

for dir_path in dir_paths:
    fp = dir_path.glob("*.raw")
    velo = os.path.basename(dir_path)
    velo = velo[:velo.index("mm")]
    for f in tqdm(fp):
        b = load_blue(str(f))
        plt.imshow(b)
        plt.savefig( str(path) +'/'+ velo + '_' +  os.path.basename(f)[:-4]  + ".png" )
        plt.clf()
        plt.close("all")
