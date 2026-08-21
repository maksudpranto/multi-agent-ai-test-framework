def login_attempt(password_correct, failed_attempts, max_attempts):
    if failed_attempts >= max_attempts:
        return "locked"
    return "success"
