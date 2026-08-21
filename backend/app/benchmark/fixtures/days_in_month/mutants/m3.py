def days_in_month(month, year):
    if month == 2:
        leap = year % 4 == 0
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31
