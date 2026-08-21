def card_not_expired(exp_month, exp_year, cur_month, cur_year):
    if exp_month < 1 or exp_month > 12:
        return "invalid"
    if exp_year < cur_year:
        return "expired"
    return "valid"
