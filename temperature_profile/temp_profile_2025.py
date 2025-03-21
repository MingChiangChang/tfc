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
    left_width_fit =  [ 5.02794524e+02,
                       2.27809447e+02,
                       -1.33599129e+01,
                       -8.12411230e+01,
                       1.76867367e-01,
                       -1.65872055e+00,
                       4.51417474e+00,
                       -5.67899883e-06]
    right_width_fit = [ 9.00132242e+02,
                       -1.60851951e+02,
                       -9.78194951e+00,
                       3.82337277e+01,
                       -4.75956003e-02,
                       2.49843621e+00]

    left_width = cubic_surface(*left_width_fit) 
    right_width = twod_surface(*right_width_fit)
    log10_velocity = np.log10(88200./tau)
    power = LaserPowerMing_Spring2025(tau, Temp, temp_fit = None)
    return left_width(log10_velocity, power), right_width(log10_velocity, power)


def LaserPowerMing_Spring2025(dwell, Tpeak, temp_fit = None):
    # print("USING POWER PROFILE MING SPRING 2024")
    if temp_fit is None:
        temp_fit = [-0.01824834, 0.05924233, -0.01709909, 0.01145558, 2.74505353]

    velo = 88200/dwell
    log10vel = np.log10(velo)
    get_power = inverse_temp_surface_func(*temp_fit) 
    power = get_power(log10vel, Tpeak)
    return power

if __name__ == '__main__':
    # print("Latest power", LaserPowerMing_Spring2025(10000, 1000))
    left_width, right_width = left_right_width(10000, 1000)
    print("Left width", left_width)
    print("Right width", right_width)
