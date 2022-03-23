'''
Functions for fitting thermal reflectance data and temperature profiles
'''

from scipy.optimize import leastsq

import cv2
import numpy as np
import matplotlib.pyplot as plt

from error_funcs import gaussian_shift

def fit_center(data, center_estimate=False, power=False,
               dwell=False, num=False, plot=False,
               savefig=False, verbose=False):
    '''
    Find the center of the gaussian with given array of data.

    Args:
        data: an array of 2D data (so 3d ndarray)

    Keyword Args:
        center_estimate: (x,y) value for estimating the center
        t, dwell, num: numbers for naming
        plot: whether to plot a figure for the fit
        savefig: whether to save the plotted figure

    Return:
        xs, ys: array of center positions
        pfit: an array of fitted parameters of the gaussian
    '''

    if center_estimate:
        params = list(moments(data))
        params[1] = center_estimate[0]
        params[2] = center_estimate[1]
        pfit, _ = fit_with(gaussian_shift, data,
                           param=params, verbose=verbose)
    else:
        pfit, _ = fit_with(gaussian_shift, data,
                           param_estimator=moments, verbose=verbose)
    fit = gaussian_shift(*pfit)
    x_s, y_s = np.indices(data.shape)
    fitted = fit(*(x_s, y_s))
    tpeak = np.max(fitted)
    center = np.where(fitted==tpeak)

    if verbose:
        print(center)
    x_center = center[0][0]
    y_center = center[1][0]

    if plot:
        _, axs = plt.subplots(4)
        axs[0].imshow(data)
        axs[1].imshow(fitted)
        axs[2].plot(fitted[x_center])
        axs[2].plot(data[x_center])
        axs[2].set_title('x fit')
        axs[3].plot(fitted[:, y_center])
        axs[3].plot(data[:, y_center])
        axs[3].set_title('y_fit')

        if savefig:
            plt.savefig(f'{power}_{dwell}_{num}.png')
        else:
            plt.show()

        plt.close()
    return x_center, y_center, pfit


def fit_xy_to_z_surface_with_func(x, y, z, func, param,
                                 uncertainty=None, verbose=False):
    '''
    fit_xy_to_z_surface_with_func(x, y, z, func, param, uncertainty, verbose)

    Use x and y to fit a quadratic surface for z.
    Input:
        x, y, z: 2d ndarrays
        func: Function to be fitted
        param: estimated parameters
        uncertainty: optional - a ndarray of the same size that describes
                                the uncertainty at each point
        verbose: optinal bool - whether to print fitting information

    Return:
        pfit: fitted parameters
        pcov: Fitted covariance matrix
        infodict: Information dictionary from scipy.optimize.leastsq

    '''
    if uncertainty is None:
        error_func = lambda p: np.ravel(func(*p)(x, y) - z)
    else:
        error_func = lambda p: np.ravel((func(*p)(x, y) - z)/uncertainty)

    pfit, pcov, infodict, errmsg, success = leastsq(error_func, param,
                                          full_output=1)
    if verbose:
        print_state(success, errmsg)

    return pfit, pcov, infodict

def self_blank(live, blank, mask):
    '''
    Fit blank using live image and a blank prototype * (linear plane)
    Mask has to be applied so that laser and residual heat is blocked
    '''
    def f(a, b, c):
        return lambda x, y: blank[mask] * (a*x + b*y + c)

    pfit, _ = fit_with(f, live, mask, param=[0, 0, 1])
    a, b, c = pfit
    x, y = np.indices(live.shape)
    return blank * (a*x + b*y + c)

def fit_mask(data, fit, thresh):
    ''' Given a fitted function fit, create a mask using the thresh value. '''
    fit_data = fit(*np.indices(data.shape))
    mask = fit_data < thresh
    #ay = np.where(np.any(~mask, axis=1))
    ax = np.where(np.any(~mask, axis=0))
    if len(ax[0]) > 1:
        dx = np.max(ax) - np.min(ax)
    else:
        dx = 0.
    print("DX", dx)
    return mask, dx*0.5

def trail(data, u = 100., v = 100., b = 100, direction='Down'):
    ''' Create a rectangular mask with intended direction. hj'''
    X, Y = np.indices(data.shape)
    if direction == 'Down':
        mask = np.logical_or((Y - v)**2 > b**2,  X < u)
    else:
        mask = np.logical_or((Y - v)**2 > b**2,  X > u)
    return mask

def ellipse(data, u = 100., v = 100., a = 100, b = 50):
    ''' Create a ellipse shape mask. '''
    X, Y = np.indices(data.shape)
    mask = (X - u)**2/a**2 + (Y - v)**2/b**2 > 1.
    return mask

def estimate_noise(img):
    '''
    Estimating the noise by calculating the difference between
    blurred img and the original one.
    '''
    #dst = cv2.filter2D(img,-1,kernel)  # pylint: disable=no-member
    blur = cv2.blur(img,(3,3))         # pylint: disable=no-member
    diff = np.abs(np.array(img).astype(float) - np.array(blur).astype(float))
    return np.sum(diff)/img.shape[0]/img.shape[1]

def surface_plot (matrix, fit, **kwargs):
    ''' Function for plotting 3D surfaces of a given matrix and the fit'''
    # acquire the cartesian coordinate matrices from the matrix
    # x is cols, y is rows
    x, y = np.meshgrid(range(matrix.shape[0]), range(matrix.shape[1]))
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    #surf0 = ax.plot_surface(x.T, y.T, np.array(matrix), alpha=0.5, cmap=plt.cm.copper)
    surf1 = ax.plot_surface(x.T, y.T, fit(*np.indices(matrix.shape)), **kwargs)
    return (fig, ax, surf1)

def moments(data):
    """
    Returns (height, x, y, width_x, width_y)
    the gaussian parameters of a 2D distribution by calculating its
    moments.
    """

    X, Y = np.indices(data.shape)
    x = (X*data).sum()/data.sum()
    y = (Y*data).sum()/data.sum()

    if x > data.shape[0] or x<0:
        x = data.shape[0]/2
    if y > data.shape[1] or y<0:
        y = data.shape[1]/2

    col = data[:, int(y)]
    width_x = np.sqrt(np.abs((np.arange(col.size)-x)**2*col).sum()/np.abs(col.sum()))
    row = data[int(x), :]
    width_y = np.sqrt(np.abs((np.arange(row.size)-y)**2*row).sum()/np.abs(row.sum()))
    height = data.max()
    rho = 0.0
    shift = 0.0
    return height, x, y, width_x, width_y, rho, shift

def default_value_approx(data):
    ''' Estimate the fitting value using the first 4 moment of the data '''
    total = data.sum()
    X, Y = np.indices(data.shape)
    x = (X*data).sum()/total
    y = (Y*data).sum()/total

    col = data[:, int(y)]
    s_x0 = np.sqrt(np.abs((np.arange(col.size)-x)**2*col).sum()/np.abs(col.sum()))
    sk_x0 = ((np.arange(col.size)-x)**3*col).sum()/s_x0**3
    ku_x0 = ((np.arange(col.size)-x)**4*col).sum()/s_x0**4-3

    row = data[int(x), :]
    s_y0 = np.sqrt(np.abs((np.arange(row.size)-y)**2*row).sum()/np.abs(row.sum()))
    sk_y0 = ((np.arange(row.size)-y)**3*row).sum()/s_y0**3
    ku_y0 = ((np.arange(row.size)-y)**4*row).sum()/s_y0**4-3
    height = data.max()
    print((f"Default height: {height}, x: {x}, y: {y}, s_x: {s_x0}, "
           f"s_y: {s_y0}, sk_x: {sk_x0}, sk_y: {sk_y0}, ku_x: {ku_x0}, "
           f"ku_y: {ku_y0}"))
    return height, x, y, s_x0, s_y0, sk_x0, sk_y0, ku_x0, ku_y0

def edgeworth_default_param_approx(data):
    ''' Function for estimating 2d edgeoworth parameters '''
    total = data.sum()
    X, Y = np.indices(data.shape)
    x = (X*data).sum()/total
    y = (Y*data).sum()/total

    col = data[:, int(y)]
    s_x0 = np.sqrt(np.abs((np.arange(col.size)-x)**2*col).sum()/np.abs(col.sum()))
    sk_x0 = ((np.arange(col.size)-x)**3*col).sum()/s_x0**3
    ku_x0 = ((np.arange(col.size)-x)**4*col).sum()/s_x0**4-3

    row = data[int(x), :]
    s_y0 = np.sqrt(np.abs((np.arange(row.size)-y)**2*row).sum()/np.abs(row.sum()))
    sk_y0 = ((np.arange(row.size)-y)**3*row).sum()/s_y0**3
    ku_y0 = ((np.arange(row.size)-y)**4*row).sum()/s_y0**4-3
    height = data.max()
    print((f"Default height: {height}, x: {x}, y: {y}, s_x: {s_x0}, "
           f"s_y: {s_y0}, sk_x: {sk_x0}, sk_y: {sk_y0}, ku_x: {ku_x0}, "
           f"ku_y: {ku_y0}"))
    return height, x, y, s_x0, s_y0, sk_x0, sk_y0, ku_x0, ku_y0

def fit_with(func, data, mask=None, param_estimator=None,
             param=None, maxfev=1000, verbose=False):
    '''
    Fit given data with given function and return the fitting
    paramters and square root of sum of error.

    Arg:
        func: function to be fitted
        data: 2d data to be fitted

    Keyward Arguments:
        mask: a boolean array with the same shape of the data to
              cover bad spots
        param_estimator: a function that estimates the param with
                         given data
        param: array of real number as the starting point of the
               least square solver
        maxfev: Int - maximum iterationfor the least square solver
        verbose: Bool - whether to print debugging info

    Return:
        pfit_leastsq: fitted parameters
        MSE: square root of sum of errors
    '''
    if param is None:
        param = param_estimator(data)
    if mask is None:
        err_func = lambda p: np.ravel(func(*p)(*np.indices(data.shape)) - data)
    else:
        X, Y = np.indices(data.shape)
        A = np.c_[X[mask], Y[mask]].T # pylint: disable=invalid-name
        err_func = lambda p: np.ravel(func(*p)(*A) - data[mask])

    pfit, pcov, _, errmsg, success = leastsq(err_func, param,
                                       full_output=1, maxfev=maxfev)

    if verbose:
        print_state(success, errmsg)

    s_sq = (err_func(pfit)**2).sum()/(len(data.flatten()))
    error = []
    #for i in range(len(pfit)):
    #    pcov = pcov * s_sq
    #    error.append(np.absolute(pcov[i][i])**0.5)
    pfit_leastsq = pfit
    #perr_leastsq = np.array(error)
    return pfit_leastsq, np.sqrt(s_sq)

def print_state(state, errmsg):
    '''Check if the state is success, if not print errmsg'''
    success_states = (1,2,3,4)
    if state in success_states:
        print('Fitting is successful.')
    else:
        print('Fitting failed.')
        print('Reason: ', errmsg)

def get_box(profile, threshold=0.6):
    '''
    Estimate the beam of the box by calculating the first two moments
    of the pixels with value larger than the threshold
    '''
    mask = profile>np.max(profile)*threshold
    a_y = np.where(np.any(mask, axis=0))
    a_x = np.where(np.any(mask, axis=1))
    x_center = np.mean(a_x)
    y_center = np.mean(a_y)
    area = np.sum(mask)
    x_r = np.sqrt(area/(3*np.pi))
    y_r = 3*x_r
    x_shift = int(x_center-2.5*x_r) if x_center-3*x_r > 0 else 0
    x_width = int(4*x_r)
    y_shift = int(y_center-2*y_r) if y_center-2*y_r > 0 else 0
    y_width = int(4*y_r)
    return x_shift, x_width, y_shift, y_width
