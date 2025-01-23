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
    left_width_fit = [ 9.23610385e+02,
                       2.31591101e+02,
                      -2.33724136e+01,
                      -6.63593631e+01,
                       2.38094452e-01,
                      -2.37653526e+00, 
                       5.05393010e+00,
                      -4.32250685e-06]
    right_width_fit =  [ 7.38857381e+02,
                        -2.47679319e+02,
                        -4.12579362e+00,
                        -2.64455714e+01,
                        -1.55386703e-01,
                         7.51253690e+00]


    left_width = cubic_surface(*left_width_fit) 
    right_width = twod_surface(*right_width_fit)
    log10_velocity = np.log10(88200./tau)
    power = LaserPowerMing_Spring2024(tau, Temp, temp_fit = None)
    return left_width(log10_velocity, power), right_width(log10_velocity, power)


def LaserPowerMing_Spring2024(dwell, Tpeak, temp_fit = None):
    print("USING POWER PROFILE MING SPRING 2024")
    if temp_fit is None:
        temp_fit = [-1.71420431e-04,  6.37694255e-04, -8.72721878e-02,  2.21288491e-01, 3.64085959e+00]

    velo = 88200/dwell
    log10vel = np.log10(velo)
    get_power = inverse_temp_surface_func(*temp_fit) 
    power = get_power(log10vel, Tpeak)
    return power

if __name__ == '__main__':
    print("Latest power", LaserPowerMing_Spring2024(10000, 1000))
    left_width, right_width = left_right_width(10000, 1000)
    print("Left width", left_width)
    print("Right width", right_width)
     
#    #pfit = [0.0022188615494199756, 0.006342578603048725, -0.0789086111648057, 0.011794630904530413, 3.1505144821012436]
#    #pfit = [0.002242187478632596, 0.006403974288925822, -0.0789010956543472, 0.011739321594370574, 3.1505871757244295]
#    #pfit = [0.0021782225129704067, 0.008989393762476278, -0.07551288955934536, 0.015642531925875964, 3.0791795850693027]
#    #pfit = [ 9.28042059e-03, -4.04355686e-04,  7.25937223e-02, -5.44852557e-01, 3.55016440e+00]
#    pfit = [0.00903015256, -0.000174216105, 0.0742548071, -0.555849208, 3.5668932]                #Fitted to gold melt
#    width_fit = [ 335.592043, -8.59771762, -4.89372480,  0.0309942213] 
#    left_width_fit  = [281.92169684,  -9.4047936 , -2.19357261]
#    right_width_fit = [211.76451937,  12.60267879, -2.53188879]
#
#    t_func = temp_surface(*pfit)
#    p_func = inverse_temp_surface(*pfit)
#    
#    dwell = 200.
#    print("Dwell", dwell)
#    log_velocity = np.log10(88200./dwell)
#    power = 49. 
#    print(f"At velocity {10**log_velocity}, power {power}W, the predicted temperature is {t_func(log_velocity, power)}")
#    print(f"The inverted power is {p_func(log_velocity, t_func(log_velocity, power))}")
#    print(p_func(log_velocity, t_func(log_velocity, power)))
#    t = constraining_func(*pfit)
#    print("Max T", t(log_velocity), LaserPowerMing_Spring2022_Tpeak_max(dwell))
#    width = width_of_left_lorentzian(*width_fit) 
#
##Inputs: log_velocity, power
#    l_width = width_of_lorentzian(*left_width_fit) 
#    r_width = width_of_lorentzian(*right_width_fit)
#
#    tau = 250
#    Temp = 1200
#    lw, rw = left_right_width(tau, Temp)
#    print("Ratio", lw, rw, lw/rw)
#    print(LaserPowerMing_Spring2022(tau, Temp))
#
#    Next_Tpeaks = [10000., 10000, 100000]
#    Next_Dwells = [100, 150, 202020]
#    #Limit the maximal Tpeak into a range that can be annealed in spring 2022
#    Next_Tpeaks_constraint = []
#    for Tpeak_i, Dwell_i in zip(Next_Tpeaks, Next_Dwells):
#        Next_Tpeaks_constraint.append(min(LaserPowerMing_Spring2022_Tpeak_max(Dwell_i), Tpeak_i))
#    print(Next_Tpeaks_constraint)
#    log10_tau = np.linspace(2, 4, 100)
#    TpMax = []
#    LinT = LaserPowerMing_Spring2022_Tpeak_max_linear(log10_tau)
#    ##for d in log10_tau:
#    ##    TpMax.append(LaserPowerMing_Spring2022_Tpeak_max(10**d))
#    ##plt.plot(log10_tau, TpMax)
#    ##plt.plot(log10_tau, LinT)
#    ##plt.show()
#    from Wafer import wafer_sample
#    s = wafer_sample()
#    wafermap = s.read_wafer_csv("CurrentWafermap.csv")
#    for i in wafermap:
#        print(i["Tpeak"], i["dwell"], i["power"])
