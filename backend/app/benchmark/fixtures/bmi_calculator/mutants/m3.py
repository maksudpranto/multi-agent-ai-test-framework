def bmi_category(weight_kg, height_m):
    bmi = weight_kg / (height_m * height_m)
    if bmi < 18.5:
        return "normal"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"
