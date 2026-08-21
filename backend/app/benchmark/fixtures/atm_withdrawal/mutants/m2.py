def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
    if amount <= 0:
        return "invalid_amount"
    if amount >= balance:
        return "insufficient_funds"
    if withdrawn_today + amount > daily_limit:
        return "over_daily_limit"
    return balance - amount
