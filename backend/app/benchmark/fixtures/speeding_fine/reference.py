def speeding_fine(speed, limit):
    if speed <= 0 or limit <= 0:
        return -1
    over = speed - limit
    if over <= 0:
        return 0
    if over <= 10:
        return 50
    if over <= 30:
        return 150
    return 300
