def weekly_pay(hours, hourly_rate):
    if hours <= 40:
        return round(hours * hourly_rate, 2)
    overtime = hours - 40
    return round(40 * hourly_rate + overtime * hourly_rate * 1.5, 2)
