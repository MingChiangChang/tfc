'''
Given the reqired temperature and quench rate,
calculate the velocity and power 
update pfit and qfit for the fitting surface of power surface and quench surface
for later fits
'''

import numpy as np
from scipy.optimize import leastsq

def temp_surface(b, c, d, e, f):
    # return lambda x, y: (a*x**2+b*x+c)*(y-yth)**(d*x**2+e*x+f) #+ (e*x+f)*(y-yth)
    return lambda x, y: (b*x+c)*(y)**(d*x**2+e*x+f)

def inverse_temp_surface(b,c,d,e,f):
    return lambda dw, t: (t/(b*dw+c))**(1/(d*dw**2 + e*dw +f))

def twod_quadratic_surface(base, a, b, c, d, e):
    ''' 2d  surface '''
    return lambda x, y: base + a*x + b*y + c*x**2 + d*y**2 + e*x*y

def get_velo_power_given_temp_quench(temp, quench):
    pfit = [0.00928042059, -0.000404355686,  0.0725937223, -0.544852557, 3.55016440]
    qfit = [ 1.87797857e+00,  1.05836154e+00,  5.66863175e-02,  5.61577321e-02, 3.85127203e-05, -1.12583431e-02]
    

    p_surf = inverse_temp_surface(*pfit)
    q_surf = twod_quadratic_surface(*qfit)

    def t(log_velo):
        p = p_surf(np.log10(log_velo), temp) 
        pred_quench = q_surf(log_velo, p) 
        return pred_quench - quench
    print(10**q_surf(np.log10(88200/5000), 40))
    velo_fit, _ = leastsq(t, [2.])
    power = p_surf(velo_fit[0], temp)
    return 10**velo_fit[0], power


if __name__ == '__main__':
    for i in np.linspace(5.5, 6.5, 10):
        print(i, get_velo_power_given_temp_quench(1414, i))

