def refund_eligibility(days_since_purchase, is_opened, price):
    if days_since_purchase >= 30:
        return "expired"
    if is_opened and price < 50:
        return "denied"
    return "approved"
