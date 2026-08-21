def validate_signup(email, password, confirm, age):
    if "@" not in email or "." not in email:
        return "invalid_email"
    if len(password) < 8:
        return "weak_password"
    if password != confirm:
        return "password_mismatch"
    if age < 18:
        return "underage"
    return "ok"
