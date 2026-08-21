def transfer(sender_balance, amount, is_frozen):
    if amount <= 0:
        return "invalid_amount"
    if is_frozen:
        return "account_frozen"
    if amount > sender_balance:
        return "insufficient_funds"
    return sender_balance - amount
