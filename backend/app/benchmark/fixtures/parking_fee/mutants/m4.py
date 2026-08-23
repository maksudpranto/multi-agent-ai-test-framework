def parking_fee(minutes):
    if minutes <= 30:
        return 0
    hours = (minutes + 59) // 60
    return 3 * hours
