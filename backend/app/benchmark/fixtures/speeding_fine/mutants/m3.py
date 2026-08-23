def speeding_fine(speed, limit):
    over = speed - limit
    if over <= 0:
        return 0
    if over <= 10:
        return 50
    if over <= 30:
        return 150
    return 300
