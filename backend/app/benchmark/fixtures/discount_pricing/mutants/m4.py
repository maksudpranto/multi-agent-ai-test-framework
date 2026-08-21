def final_price(price, discount_percent, is_member):
    if discount_percent > 100:
        return -1.0
    total = price * (1 - discount_percent / 100)
    if is_member:
        total = total * 0.9
    return round(total, 2)
