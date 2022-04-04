from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from read_raw import load_blue
from preprocess import preprocess_by_frame
from error_funcs import gaussian_shift, pseudovoigt, oned_gaussian_func, pearson3_func, two_gaussian
from error_funcs import two_lorentz
from fitting import fit_pv, fit_gaussian, fit_pearson3, fit_two_gaussian, fit_two_lorentz

if __name__ == "__main__":

    # find one frame as ref
    # fit it to function 
    # plot and see what fits best

    home = Path.home()

    path = home / "Desktop" / "TR" / "co2"

    data_path = path / "9mm per sec" / "16mm_43A_011.raw"
    bg_path = path / "9mm per sec" / "16mm_0A_011.raw"

    data = load_blue(data_path)
    bg = load_blue(bg_path)

    #fig, ax = plt.subplots(3)
    #ax[0].imshow(data)
    #ax[1].imshow(bg)
    #ax[2].imshow(data-bg)    
    plt.imshow(data-bg)
    sc = plt.colorbar()
    plt.show()

    pfit =  preprocess_by_frame(data, bg, (400, 900), (500, 1900))
    fit = gaussian_shift(*pfit)


    ymin = 500
    ymax = 1900
    #ax = plt.axes(projection='3d')
    #x, y = np.indices(data[400:900, 350:1600].shape)
    #ax.plot_wireframe(x, y, fit(x, y)-((data-bg)/bg)[400:900, 350:1600])
    #plt.show()
    r = (data-bg)/bg
    center = 400 + int(pfit[1])
    d = np.mean(r[center-20:center+20, ymin:ymax], axis=0)
    oned_fits, _ = fit_two_lorentz(d)
    f =two_lorentz(*oned_fits)
    fig, ax = plt.subplots(2, figsize=((6, 6)))
    ax[0].plot(d)
    ax[0].plot(f(np.arange(ymax-ymin)))
    ax[0].set_title("Two lorentzian with different width")

    oned_fits_2, _ = fit_pearson3(d)
    g = pearson3_func(*oned_fits_2)
    ax[1].plot(d)
    ax[1].plot(g(np.arange(ymax-ymin)))
    ax[1].set_title("Pearson3")
    ax[0].set_xticks([])
    ax[0].set_ylabel("delta R/R")
    ax[1].set_ylabel("delta R/R")
    ax[1].set_xlabel("pixel")
    plt.show()
            
