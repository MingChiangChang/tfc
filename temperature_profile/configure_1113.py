from dataclasses import dataclass

import numpy as np

@dataclass
class Configs():

    NFRAMES: int = 60
    X_DIM: int = 772 #1200 #480
    Y_DIM: int = 1024 #1920 #640
    X_MIN: int = 330#300 #200 #190
    X_MAX: int = 480#500 #300 #260
    Y_MIN: int = 60#200 #0 # 200
    Y_MAX: int = 920#800 #600 #500
    PROBE_SIZE: float = 88200. # um
    VELOCITY = np.array([9, 13, 20, 30, 45, 68, 103, 155, 234, 352], dtype=int)
    # VELOCITY = np.array([13, 20, 30, 45, 68, 103, 155, 234, 352], dtype=int)
    # Debug
    #VELOCITY = np.array([68, 103, 155, 190, 234, 352], dtype=int)

    DWELL = (PROBE_SIZE / VELOCITY).astype(int)

    POWER = {
          9: [31, 33, 35, 37, 39, 41, 43, 45, 47, 49],
         13: [31, 33, 35, 37, 39, 41, 43, 45, 47, 49],
         20: [31, 33, 35, 37, 39, 41, 43, 45, 47, 49],
         30: [33, 35, 37, 39, 41, 43, 45, 47, 49, 51],
         45: [35, 37, 39, 41, 43, 45, 47, 49, 51, 53],
         68: [37, 39, 41, 43, 45, 47, 49, 51, 53, 55, 57],
         103: [39, 41, 43, 45, 47, 49, 51, 53, 55, 57, 59, 61],
         155: [43, 45, 47, 49, 51, 53, 55, 57, 59, 61, 63, 65],
         234: [49, 51, 53, 55, 57, 59, 61, 63, 65, 67, 69, 71],
         352: [55, 57, 59, 61, 63, 65, 67, 69, 71, 73, 75, 77],
     }

    ###############
    # 111424
    # MELT = {
    #         '9':   52.15,
    #         '13':  52.5,
    #         '20':  52.9,
    #         '30':  54.9,
    #         '45':  57.0,
    #         '68':  60.1,
    #         '103': 64.15,
    #         '155': 68.5,
    #         # '190': 64.3,
    #         '234': 74.9,
    #         '352': 82.8 
    #     } 


    MELT = {'9': 49.82222212549736,
            '13': 50.88611138302031,
            '20': 51.8329571856449,
            '30': 53.241161234461835,
            '45': 56.42006472291199,
            '68': 60.14669393782391,
            '103': 63.90102693981784,
            '155': 69.07807788383622,
            '234': 75.22388079168066,
            '352': 83.06296306882786}

    # VGA setting
    N_FRAMES = {
            9: 100,
            13: 60,
            20: 60,
            30: 60,
            45: 60,
            68: 60,
            103: 60,
            155: 60,
            190: 60,
            234: 60,
            352: 60,
         }


    # Calculated by 4.5 / config.VELOCITY * 60 + 1
    # array([31.        , 21.76923077, 14.5       , 10.        ,  7.        ,
    #        4.97058824,  3.62135922,  2.74193548,  2.15384615,  1.76704545])
    FRAME = {
            9: 31,
            13: 22,
            20: 15,
            30: 10 ,
            45: 7,
            68: 5,
            103: 4,
            155: 3,
            234: 2,
            352: 2,
         }

    # Full frame setting
    # N_FRAMES = {
    #         9: 20,
    #         13: 15,
    #         20: 9,
    #         30: 7,
    #         45: 5,
    #         68: 4,
    #         103: 4,
    #         155: 4,
    #         190: 3,
    #         234: 3,
    #         352: 3,
    #      }


    # FRAME = {
    #         9: 18,
    #         13: 13,
    #         20: 8,
    #         30: 6,
    #         45: 4,
    #         68: 3,
    #         103: 2,
    #         155: 2,
    #         190: 1,
    #         234: 1,
    #         352: 1,
    #      }
    # 
