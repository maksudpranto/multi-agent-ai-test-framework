def login_attempt(password_correct, failed_attempts, max_attempts):
    if password_correct:
        return "success"
    if failed_attempts >= max_attempts:
        return "locked"
    return "denied"
