from pathlib import Path
from enum import Enum
from cv2 import imwrite
import numpy as np
import matplotlib.pyplot as plt

HEADER_LEN = 152
X_DIM = 1200 
Y_DIM = 1920 
BLUE_FILTER = np.tile(np.vstack((np.zeros(Y_DIM), np.tile([1,0], Y_DIM//2))),
                     (X_DIM//2, 1))
RED_FILTER = np.tile(np.vstack((np.tile([0, 1], Y_DIM//2), np.zeros(Y_DIM))),
                     (X_DIM//2, 1))
GREEN_FILTER = np.tile(np.vstack((np.tile([1,0], Y_DIM//2), np.tile([0, 1], Y_DIM//2))), (X_DIM//2, 1))

def load_blue(fp):
    with open(fp, 'br') as f:
        data = f.read()

    val = read_uint12(data[HEADER_LEN:])
    val = val.reshape(X_DIM, Y_DIM)
    return get_interpolation(val, Color.Blue)

def load_background_series(position: str, fps: list):
    bg_ls = []
    bg_data = []
    for fp in fps:
        _position, current, _ = parse_fn(fp)
        if is_bg(current) and position == _position:
            bg_ls.append(fp)

    for bg in tqdm(sorted(bg_ls), desc = f"Loading background at {position}"):
        bg_data.append(load_blue(bg))

    return bg_data

class Color(Enum):
    Red = 1
    Blue = 2
    Green = 3

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
def get_interpolation(data: np.array, pos_x: int, pos_y: int, color: Color):
    interpolated = np.zeros(data.shape)
    # Corners
    interpolated[0, 0] = get_corner(data[0, 0], color)
    interpolated[0, -1] = get_corner(data[0, -1], color)
    interpolated[-1, 0] = get_corner(data[-1, 0], color)
    interpolated[-1, -1] = get_corner(data[-1, -1], color)
    # Edges

# TODO: modify greens
# Assuming the dimension are even numbers...
def get_top_right_corner(data: np.array, color: Color):
    # This must be R
    if color == Color.Red:
        return data[0, -1]
    elif color == Color.Green:
        return (data[0, 0] + data[1,1])/2
    else:
        return data[0, 1]

def get_top_left_corner(data: np.array, color: Color):
    # This must be G
    if color == Color.Red:
        return data[0, 1]
    elif color == Color.Green:
        return data[0, 0]
    else:
        return data[1, 0]

def get_bottom_left_corner(data: np.array, color: Color):
    # This must be B 
    if color == Color.Blue:
        return data[-1, 0]
    elif color == Color.Red:
        return data[-2, -2]
    else:
        return (data[1, -1] + data[0, -2])/2 

def get_bottom_right_corner(data: np.array, color: Color):
    # This must be G 
    if color == Color.Green:
        return data[-1, -1] 
    elif color == Color.Red:
        return data[-2, -1]
    else:
        return data[-1, -2]

def get_blue_top_edge(data: np.array, pos_y: int):
    this_color = get_color(0, pos_y)
    if this_color == Color.Green:
        return data[1, pos_y]
    elif this_color == Color.Red:
        return (data[1, pos_y-1] + data[1, pos_y+1])/2 

def get_blue_right_edge(data: np.array, pos_x: int):
    this_color = get_color(pos_x, data.shape[1]-1)
    if this_color == Color.Green:
        return (data[-2, pos_x-1] + data[-2, pos_x+1])/2
    elif this_color == Color.Red:
        return (data[-1, pos_x-1] + data[-1, pos_x+1])/2

def get_blue_bottom_edge(data: np.array, pos_y: int):
    this_color = get_color(data.shape[0]-1, pos_y)
    if this_color == Color.Blue:
        return data[-1, pos_y] 
    elif this_color == Color.Green:
        return (data[-1, pos_y-1] + data[-1, pos_y+1])/2

def get_blue_left_edge(data: np.array, pos_x: int):
    this_color = get_color(pos_x, 0)
    if this_color == Color.Blue:
        return data[pos_x, 0] 
    elif this_color == Color.Green:
        return (data[pos_x-1, 0] + data[pos_x+1, 0])/2



def get_interpolation(data: np.array, color: Color) -> float:
    # Corners
    new_data = np.zeros(data.shape)
    new_data[0, 0] = get_top_left_corner(data, color)
    new_data[0, -1] = get_top_right_corner(data, color)
    new_data[-1, 0] = get_bottom_left_corner(data, color)
    new_data[-1, -1] = get_bottom_right_corner(data, color) 
    # Edges

    if color == Color.Blue: # TODO: Use matrix operation instead for center pixels
        blue = data * BLUE_FILTER
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
        #for pos_x in range(1, data.shape[0]-1):
        #    for pos_y in range(1, data.shape[1]-1):
        #        new_data[pos_x, pos_y] = get_b_interpolation(data, pos_x, pos_y)
    elif color == Color.Red:
        red = data * RED_FILTER
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
        green = data * GREEN_FILTER
        new_data += green 
        new_data += (   np.roll(green, (0,1), axis=(0,1))
                      + np.roll(green, (1,0), axis=(0,1))
                      + np.roll(green, (-1,0), axis=(0,1))
                      + np.roll(green, (0,-1), axis=(0,1))) /4
    return new_data
#    color = get_color(pos_x, pos_y)
#    if color == Color.Green:
#        return (data[pos_x-1, pos_y] + data[pos_x+1, pos_y])/2
#    elif color == Color.Blue:
#        return (data[pos_x-1, pos_y-1] 
#                + data[pos_x-1, pos_y+1]
#                + data[pos_x+1, pos_y-1]
#                + data[pos_x+1, pos_y+1])/4 
#    else return data[pos_x, pos_y]

def get_b_interpolation(data: np.array, pos_x: int, pos_y:int) -> float:
    color = get_color(pos_x, pos_y)
    if color == Color.Green:
        if is_odd(pos_x):
            return (data[pos_x, pos_y-1] + data[pos_x, pos_y+1])/2
        else:
            return (data[pos_x-1, pos_y] + data[pos_x+1, pos_y])/2
    elif color == Color.Red:
        return (data[pos_x-1, pos_y-1] 
                + data[pos_x-1, pos_y+1]
                + data[pos_x+1, pos_y-1]
                + data[pos_x+1, pos_y+1])/4 
    else:
        return data[pos_x, pos_y]

def get_g_interpolation(data: np.array, pos_x: int, pos_y:int) -> float:
    return

if __name__ == "__main__":
    home = Path.home()
    path = home / 'Desktop' / 'TR' / "35mm per sec" / "10mm_79A_020.raw" 
    path = home / "Downloads" / "img_+00_+00.post.raw"

    with open(path, 'br') as f:
        data = f.read()

    #d = []
    #
    #for i in data:
    #    d.append(int(str(i)))

    val = read_uint12(data[152:]) # TODO: Check why this has to be like this..
    val = val.reshape(1200, 1920)
    f = np.zeros((1200, 1920, 3)) 
    
    d = get_interpolation(val, Color.Blue)
    r = get_interpolation(val, Color.Red)
    g = get_interpolation(val, Color.Green)
    fig, ax = plt.subplots(2,2)
    ax[0, 0].imshow(val)
    ax[0, 0].set_title("Origin raw")
    ax[0, 1].imshow(d)
    ax[0, 1].set_title("blue channel")
    ax[1, 0].imshow(r)
    ax[1, 0].set_title("red channel")
    ax[1, 1].imshow(g)
    ax[1, 1].set_title("green channel")
    fig.suptitle("MURI-SARA/Thermoreflectance/2022.03 Velocity Scans/35mm per sec/10mm_79A_020.raw")
    plt.show()

    f[:,:,0] = r
    f[:,:,1] = g
    f[:,:,2] = d
    np.save("10mm_79A_20.npy", f)
    f *= (256/4096)
    print(f.shape)
    imwrite("/Users/ming/Desktop/test.bmp", f)
