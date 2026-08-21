def parse_duration(s):
    import re
    total = 0
    for num, unit in re.findall(r"(\d+)([hms])", s):
        n = int(num)
        if unit == "h":
            total += n * 60
        elif unit == "m":
            total += n * 60
        else:
            total += n
    return total
