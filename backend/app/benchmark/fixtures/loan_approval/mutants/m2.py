def loan_approval(credit_score, annual_income, loan_amount):
    if credit_score < 600:
        return "denied"
    if loan_amount > 5 * annual_income:
        return "denied"
    if credit_score > 750:
        return "approved"
    return "refer"
