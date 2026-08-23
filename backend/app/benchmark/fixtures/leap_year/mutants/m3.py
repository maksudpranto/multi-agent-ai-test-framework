def leap_year(year):
    if year < 0:
        return "invalid"
    if year % 400 == 0:
        return "leap"
    if year % 100 == 0:
        return "common"
    if year % 4 == 0:
        return "leap"
    return "common"
