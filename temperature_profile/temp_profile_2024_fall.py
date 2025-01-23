import numpy as np
from matplotlib import pyplot as plt
from scipy.optimize import leastsq

#Version 1.2, used since Feb 7 2024 at 21:24

def temp_surface_func(b, c, d, e, f):
    return lambda x, y: (b*x+c)*(y)**(d*x**2+e*x+f) + 27

def inverse_temp_surface_func(b, c, d, e, f):
    return lambda dw, t: ((t-27)/(b*dw+c))**(1/(d*dw**2 + e*dw +f))

def twod_surface(base, a, b, c, d, e):
    return lambda x, y: base + a*x + b*y + c*x**2 + d*y**2 + e*x*y

def cubic_surface(base, a, b, c, d, e, f, g):
    return lambda x, y: base + a*x + b*y + c*x**2 + d*y**2 + e*x*y + f*x**4 + g*y**4

def left_right_width(tau, Temp):
    left_width_fit = [ 6.88147388e+02,
                      -3.04477538e+02,
                      7.46639925e+00, 
                      7.85029376e+01,
                      -5.37563384e-01,
                      6.13558613e+00,
                      -4.73732102e+00,
                      4.54535809e-05]
    right_width_fit = [ 4.29641635e+02,
                       -9.27919402e+01,
                       -6.35843978e+00,
                       4.68378039e+01,
                       1.10886045e-01,
                       -2.37801825e+00]


    left_width = cubic_surface(*left_width_fit) 
    right_width = twod_surface(*right_width_fit)
    log10_velocity = np.log10(88200./tau)
    power = LaserPowerMing_Fall2024(tau, Temp, temp_fit = None)
    return left_width(log10_velocity, power), right_width(log10_velocity, power)


def LaserPowerMing_Fall2024(dwell, Tpeak, temp_fit = None):
    print("USING POWER PROFILE MING SPRING 2024")
    if temp_fit is None:
        temp_fit = [-0.00627787, 0.02098353, -0.0380434, 0.09973811, 3.04350629]

    velo = 88200/dwell
    log10vel = np.log10(velo)
    get_power = inverse_temp_surface_func(*temp_fit) 
    power = get_power(log10vel, Tpeak)
    return power

if __name__ == '__main__':
    print("Latest power", LaserPowerMing_Fall2024(10000, 1000))
    left_width, right_width = left_right_width(10000, 1000)
    print("Left width", left_width)
    print("Right width", right_width)
