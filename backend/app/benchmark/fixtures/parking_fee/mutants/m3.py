def parking_fee(minutes):
    if minutes < 0:
        return -1
    if minutes <= 60:
        return 0
    hours = (minutes + 59) // 60
    return 3 * hours
