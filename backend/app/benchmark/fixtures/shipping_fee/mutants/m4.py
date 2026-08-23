def shipping_fee(weight_kg, distance_km, is_express):
    if weight_kg <= 0 or weight_kg > 30:
        return -1.0
    fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 200)
    if is_express:
        fee = fee * 2
    return round(fee, 2)
