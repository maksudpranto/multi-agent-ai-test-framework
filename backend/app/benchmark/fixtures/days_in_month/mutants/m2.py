def days_in_month(month, year):
    if month == 2:
        leap = year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)
        return 29 if leap else 28
    if month in (4, 6, 9, 12):
        return 30
    return 31
