''' util.py'''
import os

from tqdm import tqdm

BG_CURRENT = "0W"

def is_bg(current: str):
    return current == BG_CURRENT

def sort_current(current_ls: list):
     current = [int(c[:-1]) for c in current_ls]
     current, current_ls = zip(*sorted(zip(current, current_ls)))
     return current, current_ls

def parse_fn(fn: str):
    if '/' in str(fn):
        fn = os.path.basename(fn)
    assert fn[-4:] == ".raw", f"{os.path.basename(fn)} is not a raw file."
    position, current, frame_num = fn[:-4].split('_')
    return position, current, frame_num

def get_current_position_dict(file_paths):
    current_position_dict = {}
    for file_path in list(file_paths):
        position, current, _ = parse_fn(str(file_path))
        if current not in current_position_dict:
            current_position_dict[current] = position
    return current_position_dict

def get_fn_fmt(position: str, current: str, frame_num: str):
    return f"{position}_{current}_{frame_num}"

def get_cond_from_fn(fn: str):
    if fn.endswith(".raw"):
        fn = fn[:-4]
    position, current, frame_num = fn.split('_')
    return position, current, frame_num

def get_bg_keys_at(position: str, dict_keys: list):
    bg_keys = []
    for key in keys:
        position, current, frame_num = get_cond_from_key(key)
        if position in key and is_bg(current):
            bg_key.append(key)
    return sorted(bg_keys)
