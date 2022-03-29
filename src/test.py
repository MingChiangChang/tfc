from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from read_raw import load_blue
from preprocess import preprocess_by_frame 
from fitting import fit_gaussian
home = Path.home()

path = home / "Desktop" / "TR" / "35mm per sec"  

bg_path = path / "10mm_10A_015.raw"
data_path = path / "10mm_55A_015.raw"


bg = load_blue(str(bg_path))
data = load_blue(str(data_path))

bg = np.array(bg)
data = np.array(data)
#fig, ax = plt.subplots(3)
#ax[0].imshow(bg)
#ax[1].imshow(data)
#ax[2].imshow(data-bg)
#plt.show()
temp_fit = preprocess_by_frame(data, bg, (400, 900), (350, 1600))

print(temp_fit)
t = []
x = []
for i in range(200):
    pfit = fit_gaussian(((data-bg)/bg)[int(300+i+temp_fit[1]), 350:1600])
    #plt.plot((data-bg)[int(temp_fit[1]) + 395 + i, :], label=str(i))
    print(pfit)
    t.append(pfit[0]) 
    x.append(pfit[1])
fig, ax = plt.subplots(2)
ax[1].plot(t)
ax[0].plot(x)
plt.show()
