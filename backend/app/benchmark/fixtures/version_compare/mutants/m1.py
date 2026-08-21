def compare_versions(a, b):
    pa = a.split(".")
    pb = b.split(".")
    n = max(len(pa), len(pb))
    pa += ["0"] * (n - len(pa))
    pb += ["0"] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0
