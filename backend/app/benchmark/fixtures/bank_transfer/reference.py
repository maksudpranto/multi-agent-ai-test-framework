def transfer(sender_balance, amount, is_frozen):
    if is_frozen:
        return "account_frozen"
    if amount <= 0:
        return "invalid_amount"
    if amount > sender_balance:
        return "insufficient_funds"
    return sender_balance - amount
