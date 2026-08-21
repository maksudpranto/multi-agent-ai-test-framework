def weekly_pay(hours, hourly_rate):
    if hours < 0 or hourly_rate < 0:
        return -1.0
    if hours <= 45:
        return round(hours * hourly_rate, 2)
    overtime = hours - 45
    return round(45 * hourly_rate + overtime * hourly_rate * 1.5, 2)
