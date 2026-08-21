def classify_triangle(a, b, c):
    sides = sorted([a, b, c])
    if sides[0] <= 0 or sides[0] + sides[1] < sides[2]:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "scalene"
