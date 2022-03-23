import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import leastsq, least_squares

from error_funcs import oned_gaussian_func, pseudovoigt

def fit_gaussian(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(oned_gaussian_func(*p)(x)) - data
    pfit = least_squares(err, [0.1, x.shape[0]//2, 200],
                      bounds = ([0., x.shape[0]//2 - 100, 100],
                                [0.5, x.shape[0]//2 + 100, x.shape[0]]))
    return pfit.x

def fit_pv(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(pseudovoigt(*p)(x)) - data
    pfit, _, _, _, _ = leastsq(err, [0.1, x.shape[0]//2, 200, 0.5],
            full_output=1)
    return pfit
    

if __name__ == "__main__":
    t = oned_gaussian_func(0.1, 500, 200)
    #t = pseudovoigt(0.1, 500, 200, 0.3)
    data = t(np.arange(0, 1000))
    plt.plot(t(np.arange(0, 1000)))
    plt.show()

    print( fit_gaussian(data) )
