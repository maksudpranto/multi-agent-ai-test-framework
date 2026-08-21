def weekly_pay(hours, hourly_rate):
    if hours < 0 or hourly_rate < 0:
        return -1.0
    if hours <= 40:
        return round(hours * hourly_rate, 2)
    return round(hours * hourly_rate * 1.5, 2)
