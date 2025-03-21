""" Function for dealing with Mike's raw files """
from pathlib import Path
from enum import Enum

from cv2 import imwrite
import numpy as np
import matplotlib.pyplot as plt

from util import parse_fn, is_bg


class Color(Enum):
    Red = 1
    Blue = 2
    Green = 3

class RawReader():

    def __init__(self, x_dim, y_dim, header_len = 152):
        self._x_dim = x_dim
        self._y_dim = y_dim
        self.header_len = header_len

        self.set_filters()

    @property
    def x_dim(self):
        return self._x_dim

    @x_dim.setter
    def x_dim(self, value):
        self._x_dim = value
        self.set_filters()

    @property
    def y_dim(self):
        return self._y_dim

    @y_dim.setter
    def y_dim(self, value):
        self._y_dim = value
        self.set_filters()

    def set_filters(self):
        self.blue_filter = self.get_blue_filter()
        self.red_filter = self.get_red_filter()
        self.green_filter = self.get_green_filter()

    def get_blue_filter(self):
        return np.tile(np.vstack((np.zeros(self.y_dim), np.tile([1,0], self.y_dim//2))),
                         (self.x_dim//2, 1))

    def get_red_filter(self):
        return np.tile(np.vstack((np.tile([0, 1], self.y_dim//2), np.zeros(self.y_dim))),
                     (self.x_dim//2, 1))

    def get_green_filter(self):
        return np.tile(np.vstack((np.tile([1,0], self.y_dim//2),
                                      np.tile([0, 1], self.y_dim//2))),
                           (self.x_dim//2, 1))

    def load_blue(self, fp):
        with open(fp, 'br') as f:
            data = f.read()

        val = read_uint12(data[self.header_len:])
        val = val.reshape(self.x_dim, self.y_dim)
        return get_interpolation(val, Color.Blue, self.blue_filter)


    def load_red(self, fp):
        with open(fp, 'br') as f:
            data = f.read()

        val = read_uint12(data[self.header_len:])
        val = val.reshape(self.x_dim, self.y_dim)
        return get_interpolation(val, Color.Red, self.red_filter)


    def load_green(self, fp):
        with open(fp, 'br') as f:
            data = f.read()

        val = read_uint12(data[self.header_len:])
        val = val.reshape(self.x_dim, self.y_dim)
        return get_interpolation(val, Color.Green, self.green_filter)



# def load_blue(fp, ):
#     with open(fp, 'br') as f:
#         data = f.read()
# 
#     val = read_uint12(data[HEADER_LEN:])
#     val = val.reshape(X_DIM, Y_DIM)
#     return get_interpolation(val, Color.Blue)


def read_uint12(data_chunk):
    """ For little endien"""
    data = np.frombuffer(data_chunk, dtype=np.uint8)
    fst_uint8, snd_uint8 = np.reshape(data, (data.shape[0] // 2, 2)).astype(np.uint16).T
    uint12 = fst_uint8 + (snd_uint8 << 8)
    return uint12 

def is_odd(i):
    return i % 2 == 1

def is_even(i):
    return not is_odd(i)

def get_color(pos_x: int, pos_y: int) -> Color:
    if (is_odd(pos_x) and is_odd(pos_y)) or (is_even(pos_x) and is_even(pos_y)):
        return Color.Green
    elif is_odd(pos_y):  
        return Color.Red
    else:
        return Color.Blue

# TODO: Bound check 

# def get_interpolation(data: np.ndarray, pos_x: int, pos_y: int, color: Color):
#     interpolated = np.zeros(data.shape)
#     # Corners
#     interpolated[0, 0] = get_corner(data[0, 0], color)
#     interpolated[0, -1] = get_corner(data[0, -1], color)
#     interpolated[-1, 0] = get_corner(data[-1, 0], color)
#     interpolated[-1, -1] = get_corner(data[-1, -1], color)
#     # Edges

# TODO: modify greens
# Assuming the dimension are even numbers...
def get_top_right_corner(data: np.ndarray, color: Color):
    # This must be R
    if color == Color.Red:
        return data[0, -1]
    elif color == Color.Green:
        return (data[0, 0] + data[1,1])/2
    else:
        return data[0, 1]

def get_top_left_corner(data: np.ndarray, color: Color):
    # This must be G
    if color == Color.Red:
        return data[0, 1]
    elif color == Color.Green:
        return data[0, 0]
    else:
        return data[1, 0]

def get_bottom_left_corner(data: np.ndarray, color: Color):
    # This must be B 
    if color == Color.Blue:
        return data[-1, 0]
    elif color == Color.Red:
        return data[-2, -2]
    else:
        return (data[1, -1] + data[0, -2])/2 

def get_bottom_right_corner(data: np.ndarray, color: Color):
    # This must be G 
    if color == Color.Green:
        return data[-1, -1] 
    elif color == Color.Red:
        return data[-2, -1]
    else:
        return data[-1, -2]


def get_blue_top_edge(data: np.ndarray, pos_y: int):
    this_color = get_color(0, pos_y)
    if this_color == Color.Green:
        return data[1, pos_y]
    elif this_color == Color.Red:
        return (data[1, pos_y-1] + data[1, pos_y+1])/2 


def get_blue_right_edge(data: np.ndarray, pos_x: int):
    this_color = get_color(pos_x, data.shape[1]-1)
    if this_color == Color.Green:
        return (data[-2, pos_x-1] + data[-2, pos_x+1])/2
    elif this_color == Color.Red:
        return (data[-1, pos_x-1] + data[-1, pos_x+1])/2


def get_blue_bottom_edge(data: np.ndarray, pos_y: int):
    this_color = get_color(data.shape[0]-1, pos_y)
    if this_color == Color.Blue:
        return data[-1, pos_y] 
    elif this_color == Color.Green:
        return (data[-1, pos_y-1] + data[-1, pos_y+1])/2


def get_blue_left_edge(data: np.ndarray, pos_x: int):
    this_color = get_color(pos_x, 0)
    if this_color == Color.Blue:
        return data[pos_x, 0] 
    elif this_color == Color.Green:
        return (data[pos_x-1, 0] + data[pos_x+1, 0])/2


def get_interpolation(data: np.ndarray, color: Color, _filter: np.ndarray) -> np.ndarray:
    # Corners
    new_data = np.zeros(data.shape)
    new_data[0, 0] = get_top_left_corner(data, color)
    new_data[0, -1] = get_top_right_corner(data, color)
    new_data[-1, 0] = get_bottom_left_corner(data, color)
    new_data[-1, -1] = get_bottom_right_corner(data, color) 

    if color == Color.Blue: # TODO: Use matrix operation instead for center pixels
        blue = data * _filter #BLUE_FILTER
        for i in range(1, data.shape[1]-1):
            new_data[0, i] = get_blue_top_edge(data, i)
            new_data[-1, i] = get_blue_bottom_edge(data, i)
        for i in range(1, data.shape[0]-1):
            new_data[i, 0] = get_blue_left_edge(data, i)
            new_data[i, -1] = get_blue_right_edge(data, i) 
        new_data[1:-1, 1:-1] += blue[1:-1, 1:-1]
        new_data[1:-1, 1:-1] += ( (np.roll(blue, 1, axis=1) 
                                  + np.roll(blue, -1, axis=1)
                                  + np.roll(blue, 1, axis=0) 
                                  + np.roll(blue, -1, axis=0))/2
                                + ( np.roll(blue, (1,1), axis=(0,1))
                                  + np.roll(blue, (-1,1), axis=(0,1))
                                  + np.roll(blue, (1,-1), axis=(0,1))
                                  + np.roll(blue, (-1,-1), axis=(0,1))) /4 
                               )[1:-1, 1:-1]
    elif color == Color.Red:
        red = data * _filter #RED_FILTER
        new_data += red 
        new_data += ( (np.roll(red, 1, axis=1)
                        + np.roll(red, -1, axis=1)
                        + np.roll(red, 1, axis=0)
                        + np.roll(red, -1, axis=0))/2
                      + ( np.roll(red, (1,1), axis=(0,1))
                        + np.roll(red, (-1,1), axis=(0,1))
                        + np.roll(red, (1,-1), axis=(0,1))
                        + np.roll(red, (-1,-1), axis=(0,1))) /4)
    elif color == Color.Green:
        green = data * _filter #GREEN_FILTER
        new_data += green 
        new_data += (   np.roll(green, (0,1), axis=(0,1))
                      + np.roll(green, (1,0), axis=(0,1))
                      + np.roll(green, (-1,0), axis=(0,1))
                      + np.roll(green, (0,-1), axis=(0,1))) /4
    return new_data


# def get_b_interpolation(data: np.ndarray, pos_x: int, pos_y:int) -> float:
#     color = get_color(pos_x, pos_y)
#     if color == Color.Green:
#         if is_odd(pos_x):
#             return (data[pos_x, pos_y-1] + data[pos_x, pos_y+1])/2
#         else:
#             return (data[pos_x-1, pos_y] + data[pos_x+1, pos_y])/2
#     elif color == Color.Red:
#         return (data[pos_x-1, pos_y-1] 
#                 + data[pos_x-1, pos_y+1]
#                 + data[pos_x+1, pos_y-1]
#                 + data[pos_x+1, pos_y+1])/4 
#     else:
#         return data[pos_x, pos_y]

# def get_g_interpolation(data: np.ndarray, pos_x: int, pos_y:int) -> float:
#     return

if __name__ == "__main__":
    home = Path.home()
    path = home / 'Desktop' / 'TR' / "35mm per sec" / "10mm_79A_020.raw" 
    path = home / "Downloads" / "img_+00_+00.post.raw"
    path = home / "Desktop" / "09800us_029.00W"

    bg = path.glob("*.raw")
    bgs = np.zeros((6, 1200, 1920))
    for idx, b in enumerate(bg):
        print(idx)
        bgs[idx] = load_blue(b)
        
    avg_bg = np.mean(bgs, axis=0)
    single_bg = bgs[1] 

    fig, ax = plt.subplots(2)
    ax[0].plot(avg_bg[600,:-5])
    ax[1].plot(bgs[1, 600,:-5])
    plt.show()
