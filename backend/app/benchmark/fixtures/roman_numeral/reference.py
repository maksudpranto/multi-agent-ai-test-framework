def int_to_roman(n):
    vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    out = []
    for v, s in zip(vals, syms):
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)
