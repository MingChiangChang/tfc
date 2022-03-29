def sort_current(current_ls: list):
     current = [int(c[:-1]) for c in current_ls]
     current, current_ls = zip(*sorted(zip(current, current_ls)))
     return current, current_ls
