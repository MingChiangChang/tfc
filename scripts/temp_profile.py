import numpy as np

def temp_surface(b, c, d, e, f):
    # return lambda x, y: (a*x**2+b*x+c)*(y-yth)**(d*x**2+e*x+f) #+ (e*x+f)*(y-yth)
    return lambda x, y: (b*x+c)*(y)**(d*x**2+e*x+f)

def inverse_temp_surface(b,c,d,e,f):
    return lambda dw, t: (t/(b*dw+c))**(1/(d*dw**2 + e*dw +f))

def constraining_func(b, c, d, e, f):
    return lambda log_velo: min(1414, (b*log_velo+c)*(63.5)**(d*log_velo**2+e*log_velo+f))

def width_of_lorentzian(a, b, c):
    return lambda log_velo, power: a + b*log_velo + c*power


if __name__ == '__main__':
    #pfit = [0.0022188615494199756, 0.006342578603048725, -0.0789086111648057, 0.011794630904530413, 3.1505144821012436]
    #pfit = [0.002242187478632596, 0.006403974288925822, -0.0789010956543472, 0.011739321594370574, 3.1505871757244295]
    #pfit = [0.0021782225129704067, 0.008989393762476278, -0.07551288955934536, 0.015642531925875964, 3.0791795850693027]
    #pfit = [0.008180749998066969, 0.0014211463084623367, -0.03602271659769682, -0.22352876075428466, 3.3681170665099858]
    #pfit = [0.009273520030248802, 0.0016115282839335686, -0.03602545696459194, -0.22351445136516912, 3.368100525699449]
    #pfit =  [0.0017380204131135426, 0.01182884580650933, -0.07755892460176421, 0.03870934418528416, 3.0347475507057315]
    
    pfit_ming = [ 9.28042059e-03, -4.04355686e-04,  7.25937223e-02, -5.44852557e-01, 3.55016440e+00] # 0415 Ming
    pfit = [ 9.03015256e-03, -1.74216105e-04,  7.42548071e-02, -5.55849208e-01,
  3.56689320e+00] # 0417 duncan
    pfit_bio2 = [ 8.68714695e-03, 1.60681996e-03, -2.38315795e-02, -2.65700373e-01,
    3.40458695e+00]
    left_width_fit  = [281.92169684,  -9.4047936 , -2.19357261]
    right_width_fit = [211.76451937,  12.60267879, -2.53188879]
    t_func = temp_surface(*pfit)
    p_func = inverse_temp_surface(*pfit)
    p_func_bi = inverse_temp_surface(*pfit_bio2)
    p_func_ming = inverse_temp_surface(*pfit_ming) 
    log_velocity = np.log10(9)
    power = 49 
    print(f"At velocity {10**log_velocity}, power {power}W, the predicted temperature is {t_func(log_velocity, power)}")
    print(f"The inverted power is {p_func(log_velocity, t_func(log_velocity, power))}")
    t = constraining_func(*pfit)
    l_width = width_of_lorentzian(*left_width_fit) 
    r_width = width_of_lorentzian(*right_width_fit)

    print(l_width(np.log10(350), 63))
    print(r_width(np.log10(350), 63))
