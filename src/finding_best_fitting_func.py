from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from new_process import load_blue
from preprocess import preprocess_by_frame
from error_funcs import gaussian_shift, pseudovoigt, oned_gaussian_func
from fitting import fit_pv, fit_gaussian

if __name__ == "__main__":

    # find one frame as ref
    # fit it to function 
    # plot and see what fits best

    home = Path.home()

    path = home / "Desktop" / "TR"

    data_path = path / "15mm per sec" / "-22mm_71A_011.raw"
    bg_path = path / "15mm per sec" / "-22mm_10A_011.raw"

    data = load_blue(data_path)
    bg = load_blue(bg_path)

    #fig, ax = plt.subplots(3)
    #ax[0].imshow(data)
    #ax[1].imshow(bg)
    #ax[2].imshow(data-bg)    
    #plt.show()

    pfit =  preprocess_by_frame(data, bg, (400, 900), (350, 1600))
    print(pfit)
    fit = gaussian_shift(*pfit)
    
    #fig = plt.figure()
    #ax = plt.axes(projection='3d')
    #x, y = np.indices(data[400:900, 350:1600].shape)
    #ax.plot_wireframe(x, y, fit(x, y)-((data-bg)/bg)[400:900, 350:1600])
    #plt.show()
    r = (data-bg)/bg
    oned_fits = fit_gaussian(r[int(400+pfit[1]), 350:1600])
    f = oned_gaussian_func(*oned_fits)
    fig, ax = plt.subplots(2)
    ax[0].plot(r[int(400+pfit[1]), 350:1600])
    ax[0].plot(f(np.arange(1600-350)))
    oned_fits_2 = fit_pv(r[int(400+pfit[1]), 350:1600])
    g = pseudovoigt(*oned_fits_2)
    ax[1].plot(r[int(400+pfit[1]), 350:1600])
    ax[1].plot(g(np.arange(1600-350)))

    plt.show()
            
