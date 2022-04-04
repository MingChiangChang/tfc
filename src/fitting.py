import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import leastsq, least_squares
from scipy.stats import pearson3

from error_funcs import oned_gaussian_func, pseudovoigt, pearson3_func, two_gaussian, two_lorentz

def fit_gaussian(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(oned_gaussian_func(*p)(x)) - data
    pfit = least_squares(err, [0.1, x.shape[0]//2, x.shape[0]/2],
                      bounds = ([0., x.shape[0]//2 - 300, 0],
                                [0.5, x.shape[0]//2 + 300, x.shape[0]*3]))
    s_sq = ((oned_gaussian_func(*pfit.x)(x)-data)**2).sum()/(x.shape[0]-len(pfit.x))
    pcov = pfit.jac.T @ pfit.jac
    pcov = pcov * s_sq
    error = []
    for i in range(len(pfit.x)):
        try:
          error.append(np.absolute(pcov[i][i])**0.5)
        except:
          error.append( 0.00 )
    return pfit.x, np.array(error)

def fit_pv(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(pseudovoigt(*p)(x)) - data
    pfit, _, _, _, _ = leastsq(err, [0.1, x.shape[0]//2, 200, 0.5],
            full_output=1)
    return pfit


def fit_pearson3(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(pearson3_func(*p)(x)) - data
    pfit, _, _, _, _ = leastsq(err, [0.1, 0.1, x.shape[0]//2, 200],
             full_output=1)
    #pfit = least_squares(err, [0.1, 0.1, x.shape[0]//2, x.shape[0]//2],
    #                  bounds = ([0., 0., x.shape[0]//2 - 300, 0],
    #                            [0.5, 10., x.shape[0]//2 + 300, x.shape[0]*3]))
    #s_sq = ((pearson3_func(*pfit.x)(x)-data)**2).sum()/(x.shape[0]-len(pfit.x))
    #pcov = pfit.jac.T @ pfit.jac
    #pcov = pcov * s_sq
    #error = []
    #for i in range(len(pfit.x)):
    #    try:
    #      error.append(np.absolute(pcov[i][i])**0.5)
    #    except:
    #      error.append( 0.00 )
    print(pfit)
    return pfit, 123    

def fit_two_gaussian(data):
    x = np.arange(data.shape[0])    
    err = lambda p: np.ravel(two_gaussian(*p)(x)) - data
    pfit, _, _, _, _ = leastsq(err, [0.1, x.shape[0]//2, 200, 200],
             full_output=1)
    print(pfit)
    return pfit, 123

def fit_two_lorentz(data):
    x = np.arange(data.shape[0])
    err = lambda p: np.ravel(two_lorentz(*p)(x)) - data
    #pfit, _, _, _, _ = leastsq(err, [0.1, x.shape[0]//2, 200, 200],
    #         full_output=1)
    pfit = least_squares(err, [0.1, x.shape[0]//2, 500, 300],
                      bounds = ([0.,  x.shape[0]//2 - 300,    0.,    0.],
                                [0.4, x.shape[0]//2 + 300, 1000., 1000.]))
    s_sq = ((two_lorentz(*pfit.x)(x)-data)**2).sum()/(x.shape[0]-len(pfit.x))
    pcov = pfit.jac.T @ pfit.jac
    pcov = pcov * s_sq
    error = []
    for i in range(len(pfit.x)):
        try:
          error.append(np.absolute(pcov[i][i])**0.5)
        except:
          error.append( 0.00 )
    return pfit.x, np.array(error)

if __name__ == "__main__":
    t = oned_gaussian_func(0.1, 500, 200)
    #t = pseudovoigt(0.1, 500, 200, 0.3)
    data = t(np.arange(0, 1000))
    plt.plot(t(np.arange(0, 1000)))
    plt.show()

    print( fit_gaussian(data) )
