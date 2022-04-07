from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from read_raw import load_blue
from preprocess import preprocess_by_frame 
from fitting import fit_gaussian
from error_funcs import oned_gaussian_func
home = Path.home()

path = home / "Desktop" / "TR" / "co2" / "9mm per sec"  

bg_path = path / "16mm_0A_015.raw"
data_path = path / "16mm_43A_015.raw"


bg = load_blue(str(bg_path))
data = load_blue(str(data_path))

bg = np.array(bg)
data = np.array(data)
#fig, ax = plt.subplots(3)
#ax[0].imshow(bg)
#ax[1].imshow(data)
#ax[2].imshow(data-bg)
#plt.show()
temp_fit = preprocess_by_frame(data, bg, (600, 900), (800, 1600))

print(temp_fit)
t = []
x = []
for i in range(200):
    pfit, _ = fit_gaussian(((data-bg)/bg)[int(500+i+temp_fit[1]), 800:1600])
    print(pfit)
    #plt.plot(((data-bg)/bg)[int(temp_fit[1]) + 500 + i, 800:1600], label=str(i))
    xx = np.arange(800)
    #plt.plot(xx, oned_gaussian_func(*pfit)(xx))
    #plt.show()
    t.append(pfit[0]) 
    x.append(pfit[1])
fig, ax = plt.subplots(2)
ax[1].plot(t)
ax[0].plot(x)
plt.show()
