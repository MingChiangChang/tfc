from pathlib import Path
import os

from tqdm import tqdm
import matplotlib.pyplot as plt

from read_raw import load_blue

home = Path.home() 
path = home / "Desktop" / "TR" 
dir_path = path / "35mm per sec"

fp = dir_path.glob("*.raw")

for f in tqdm(fp):
    b = load_blue(str(f))
    plt.imshow(b)
    plt.savefig( str(path) + os.path.basename(f)[:-4]  + ".png" )
    plt.close()
