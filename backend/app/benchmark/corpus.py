"""The executable micro-benchmark corpus (authoritative source).

Each entry is a small, pure Python function drawn from a REAL-WORLD feature a QA
engineer would test — ATM withdrawal, login lockout, signup validation, a bank
transfer, discount pricing, ticket booking, payroll overtime, card expiry. Each
carries:
  - a natural-language `requirement` the pipeline generates tests from,
  - an `entrypoint` + `signature` the fault-detection harness calls,
  - a correct `reference` implementation that acts as the test ORACLE,
  - `canonical_inputs`: deterministic fallback argument lists (comprehensive
    enough to kill every mutant), and
  - four `mutants`: the reference with one deliberate, edge-targeted bug.

Why model real features as small functions? Because the *business logic* of a
feature — "you can't withdraw more than your daily limit", "a locked account
stays locked even with the right password" — is exactly what a test case checks,
and it is small and pure enough to execute and to plant bugs in. That keeps the
benchmark both **relatable** (an examiner recognises the scenarios instantly) and
**executable** (we can actually run the tests and count caught bugs).

Design for a fair, discriminating benchmark:
  * The requirements read like real requirements — they state the core behaviour
    but do not enumerate every corner case. The edges (a zero/negative amount, an
    exact boundary, a locked-but-correct-password login) must be *discovered* by a
    thorough tester, which is the work the multi-agent analysis + debate is meant
    to do.
  * Each mutant hides in one such edge, so it is killed ONLY by an input that
    exercises that edge. A thin suite kills the obvious mutants and misses the
    edge ones; a suite that covers the corners kills more.

`seed.py` loads these into the DB. `build_fixtures()` also materializes a
reviewable on-disk `fixtures/<slug>/` + `manifest.json` layout for the thesis
appendix; the runtime path does not depend on those files existing.
"""
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

PROGRAMS: list[dict] = [
    {
        "slug": "atm_withdrawal",
        "title": "ATM cash withdrawal",
        "entrypoint": "atm_withdraw",
        "signature": "atm_withdraw(balance: int, amount: int, withdrawn_today: int, daily_limit: int) -> int | str",
        "params": [
            {"name": "balance", "type": "int", "note": "current account balance"},
            {"name": "amount", "type": "int", "note": "requested withdrawal amount"},
            {"name": "withdrawn_today", "type": "int", "note": "already withdrawn today"},
            {"name": "daily_limit", "type": "int", "note": "maximum allowed per day"},
        ],
        "requirement": dedent(
            """\
            As a bank customer at an ATM, I want to withdraw cash from my account.

            The machine gives me the money and returns my new balance, as long as I
            have enough in my account and I stay within my daily withdrawal limit.
            If something is wrong it tells me why instead: "invalid_amount",
            "insufficient_funds", or "over_daily_limit"."""
        ),
        "canonical_inputs": [
            [1000, 200, 0, 500], [1000, 0, 0, 500], [1000, -50, 0, 500],
            [100, 200, 0, 500], [1000, 1000, 0, 5000], [1000, 300, 400, 500],
            [1000, 100, 400, 500],
        ],
        "reference": dedent(
            '''\
            def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
                if amount <= 0:
                    return "invalid_amount"
                if amount > balance:
                    return "insufficient_funds"
                if withdrawn_today + amount > daily_limit:
                    return "over_daily_limit"
                return balance - amount
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Allows a zero withdrawal (checks < 0 instead of <= 0).",
             "code": dedent(
                '''\
                def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
                    if amount < 0:
                        return "invalid_amount"
                    if amount > balance:
                        return "insufficient_funds"
                    if withdrawn_today + amount > daily_limit:
                        return "over_daily_limit"
                    return balance - amount
                ''')},
            {"key": "m2", "description": "Rejects withdrawing the exact balance (uses >= instead of >).",
             "code": dedent(
                '''\
                def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
                    if amount <= 0:
                        return "invalid_amount"
                    if amount >= balance:
                        return "insufficient_funds"
                    if withdrawn_today + amount > daily_limit:
                        return "over_daily_limit"
                    return balance - amount
                ''')},
            {"key": "m3", "description": "Rejects hitting the daily limit exactly (uses >= instead of >).",
             "code": dedent(
                '''\
                def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
                    if amount <= 0:
                        return "invalid_amount"
                    if amount > balance:
                        return "insufficient_funds"
                    if withdrawn_today + amount >= daily_limit:
                        return "over_daily_limit"
                    return balance - amount
                ''')},
            {"key": "m4", "description": "Skips the daily-limit check entirely.",
             "code": dedent(
                '''\
                def atm_withdraw(balance, amount, withdrawn_today, daily_limit):
                    if amount <= 0:
                        return "invalid_amount"
                    if amount > balance:
                        return "insufficient_funds"
                    return balance - amount
                ''')},
        ],
    },
    {
        "slug": "login_lockout",
        "title": "Login with account lockout",
        "entrypoint": "login_attempt",
        "signature": "login_attempt(password_correct: bool, failed_attempts: int, max_attempts: int) -> str",
        "params": [
            {"name": "password_correct", "type": "bool", "note": "whether the entered password matches"},
            {"name": "failed_attempts", "type": "int", "note": "consecutive failures so far"},
            {"name": "max_attempts", "type": "int", "note": "how many failures trigger a lock"},
        ],
        "requirement": dedent(
            """\
            As a security feature, I want a login check that locks an account after too
            many failed attempts.

            Given whether the password is correct and how many times it has already
            failed, return "success" on a correct password, "denied" on a wrong one,
            and "locked" once the account has reached the maximum failed attempts."""
        ),
        "canonical_inputs": [
            [True, 0, 3], [False, 0, 3], [True, 3, 3], [False, 3, 3],
            [True, 2, 3], [False, 4, 3],
        ],
        "reference": dedent(
            '''\
            def login_attempt(password_correct, failed_attempts, max_attempts):
                if failed_attempts >= max_attempts:
                    return "locked"
                if password_correct:
                    return "success"
                return "denied"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Checks the password before the lock, so a correct password unlocks a locked account.",
             "code": dedent(
                '''\
                def login_attempt(password_correct, failed_attempts, max_attempts):
                    if password_correct:
                        return "success"
                    if failed_attempts >= max_attempts:
                        return "locked"
                    return "denied"
                ''')},
            {"key": "m2", "description": "Off-by-one on the lock threshold (uses > instead of >=).",
             "code": dedent(
                '''\
                def login_attempt(password_correct, failed_attempts, max_attempts):
                    if failed_attempts > max_attempts:
                        return "locked"
                    if password_correct:
                        return "success"
                    return "denied"
                ''')},
            {"key": "m3", "description": "A locked account returns 'denied' instead of 'locked'.",
             "code": dedent(
                '''\
                def login_attempt(password_correct, failed_attempts, max_attempts):
                    if failed_attempts >= max_attempts:
                        return "denied"
                    if password_correct:
                        return "success"
                    return "denied"
                ''')},
            {"key": "m4", "description": "Ignores the password and always reports success when not locked.",
             "code": dedent(
                '''\
                def login_attempt(password_correct, failed_attempts, max_attempts):
                    if failed_attempts >= max_attempts:
                        return "locked"
                    return "success"
                ''')},
        ],
    },
    {
        "slug": "signup_validation",
        "title": "Sign-up form validation",
        "entrypoint": "validate_signup",
        "signature": "validate_signup(email: str, password: str, confirm: str, age: int) -> str",
        "params": [
            {"name": "email", "type": "str", "note": "the email address entered"},
            {"name": "password", "type": "str", "note": "the chosen password"},
            {"name": "confirm", "type": "str", "note": "the password typed again"},
            {"name": "age", "type": "int", "note": "the user's age in years"},
        ],
        "requirement": dedent(
            """\
            As a sign-up form, I want to validate a new registration before creating the
            account.

            The email must look like an email, the password must be at least 8
            characters and match the confirmation, and the user must be at least 18.
            Return "ok" if everything passes, otherwise the first problem found:
            "invalid_email", "weak_password", "password_mismatch", or "underage"."""
        ),
        "canonical_inputs": [
            ["a@b.com", "password1", "password1", 25],
            ["bad-email", "password1", "password1", 25],
            ["a@bcom", "password1", "password1", 25],
            ["a@b.com", "short", "short", 25],
            ["a@b.com", "1234567", "1234567", 25],
            ["a@b.com", "password1", "different", 25],
            ["a@b.com", "password1", "password1", 16],
            ["a@b.com", "password1", "password1", 18],
        ],
        "reference": dedent(
            '''\
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
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Treats 18-year-olds as underage (uses <= 18).",
             "code": dedent(
                '''\
                def validate_signup(email, password, confirm, age):
                    if "@" not in email or "." not in email:
                        return "invalid_email"
                    if len(password) < 8:
                        return "weak_password"
                    if password != confirm:
                        return "password_mismatch"
                    if age <= 18:
                        return "underage"
                    return "ok"
                ''')},
            {"key": "m2", "description": "Accepts 7-character passwords (uses < 7 instead of < 8).",
             "code": dedent(
                '''\
                def validate_signup(email, password, confirm, age):
                    if "@" not in email or "." not in email:
                        return "invalid_email"
                    if len(password) < 7:
                        return "weak_password"
                    if password != confirm:
                        return "password_mismatch"
                    if age < 18:
                        return "underage"
                    return "ok"
                ''')},
            {"key": "m3", "description": "Skips the password-confirmation check.",
             "code": dedent(
                '''\
                def validate_signup(email, password, confirm, age):
                    if "@" not in email or "." not in email:
                        return "invalid_email"
                    if len(password) < 8:
                        return "weak_password"
                    if age < 18:
                        return "underage"
                    return "ok"
                ''')},
            {"key": "m4", "description": "Only checks for '@' in the email, not a dot.",
             "code": dedent(
                '''\
                def validate_signup(email, password, confirm, age):
                    if "@" not in email:
                        return "invalid_email"
                    if len(password) < 8:
                        return "weak_password"
                    if password != confirm:
                        return "password_mismatch"
                    if age < 18:
                        return "underage"
                    return "ok"
                ''')},
        ],
    },
    {
        "slug": "discount_pricing",
        "title": "Checkout discount pricing",
        "entrypoint": "final_price",
        "signature": "final_price(price: float, discount_percent: float, is_member: bool) -> float",
        "params": [
            {"name": "price", "type": "float", "note": "the pre-discount price"},
            {"name": "discount_percent", "type": "float", "note": "percentage discount, 0-100"},
            {"name": "is_member", "type": "bool", "note": "whether the shopper is a member"},
        ],
        "requirement": dedent(
            """\
            As a shopping cart, I want to compute the final price after a discount.

            Apply the percentage discount to the price, and give members an extra 10%
            off on top. The discount percentage must be between 0 and 100 — if it is
            not, return -1 to signal an invalid discount. Round the result to 2
            decimals."""
        ),
        "canonical_inputs": [
            [100, 20, False], [100, 20, True], [100, 0, False],
            [100, 100, False], [100, 150, False], [100, -10, False],
        ],
        "reference": dedent(
            '''\
            def final_price(price, discount_percent, is_member):
                if discount_percent < 0 or discount_percent > 100:
                    return -1.0
                total = price * (1 - discount_percent / 100)
                if is_member:
                    total = total * 0.9
                return round(total, 2)
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "No upper bound on the discount, so over-100% discounts go through.",
             "code": dedent(
                '''\
                def final_price(price, discount_percent, is_member):
                    if discount_percent < 0:
                        return -1.0
                    total = price * (1 - discount_percent / 100)
                    if is_member:
                        total = total * 0.9
                    return round(total, 2)
                ''')},
            {"key": "m2", "description": "Forgets the extra member discount.",
             "code": dedent(
                '''\
                def final_price(price, discount_percent, is_member):
                    if discount_percent < 0 or discount_percent > 100:
                        return -1.0
                    total = price * (1 - discount_percent / 100)
                    return round(total, 2)
                ''')},
            {"key": "m3", "description": "Adds the discount instead of subtracting it.",
             "code": dedent(
                '''\
                def final_price(price, discount_percent, is_member):
                    if discount_percent < 0 or discount_percent > 100:
                        return -1.0
                    total = price * (1 + discount_percent / 100)
                    if is_member:
                        total = total * 0.9
                    return round(total, 2)
                ''')},
            {"key": "m4", "description": "No check for a negative discount.",
             "code": dedent(
                '''\
                def final_price(price, discount_percent, is_member):
                    if discount_percent > 100:
                        return -1.0
                    total = price * (1 - discount_percent / 100)
                    if is_member:
                        total = total * 0.9
                    return round(total, 2)
                ''')},
        ],
    },
    {
        "slug": "bank_transfer",
        "title": "Bank account transfer",
        "entrypoint": "transfer",
        "signature": "transfer(sender_balance: int, amount: int, is_frozen: bool) -> int | str",
        "params": [
            {"name": "sender_balance", "type": "int", "note": "the sender's balance"},
            {"name": "amount", "type": "int", "note": "amount to transfer"},
            {"name": "is_frozen", "type": "bool", "note": "whether the sender account is frozen"},
        ],
        "requirement": dedent(
            """\
            As an online banking feature, I want to transfer money out of an account.

            A frozen account cannot transfer at all. Otherwise the amount must be
            positive and no more than the balance; on success return the sender's new
            balance. Report problems as "account_frozen", "invalid_amount", or
            "insufficient_funds"."""
        ),
        "canonical_inputs": [
            [500, 100, False], [500, 100, True], [500, 0, False],
            [500, 600, False], [500, 500, False], [500, 0, True],
        ],
        "reference": dedent(
            '''\
            def transfer(sender_balance, amount, is_frozen):
                if is_frozen:
                    return "account_frozen"
                if amount <= 0:
                    return "invalid_amount"
                if amount > sender_balance:
                    return "insufficient_funds"
                return sender_balance - amount
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Checks the amount before the freeze, so a frozen account can surface other errors.",
             "code": dedent(
                '''\
                def transfer(sender_balance, amount, is_frozen):
                    if amount <= 0:
                        return "invalid_amount"
                    if is_frozen:
                        return "account_frozen"
                    if amount > sender_balance:
                        return "insufficient_funds"
                    return sender_balance - amount
                ''')},
            {"key": "m2", "description": "Allows a zero transfer (checks < 0 instead of <= 0).",
             "code": dedent(
                '''\
                def transfer(sender_balance, amount, is_frozen):
                    if is_frozen:
                        return "account_frozen"
                    if amount < 0:
                        return "invalid_amount"
                    if amount > sender_balance:
                        return "insufficient_funds"
                    return sender_balance - amount
                ''')},
            {"key": "m3", "description": "Rejects transferring the whole balance (uses >= instead of >).",
             "code": dedent(
                '''\
                def transfer(sender_balance, amount, is_frozen):
                    if is_frozen:
                        return "account_frozen"
                    if amount <= 0:
                        return "invalid_amount"
                    if amount >= sender_balance:
                        return "insufficient_funds"
                    return sender_balance - amount
                ''')},
            {"key": "m4", "description": "Ignores the frozen flag entirely.",
             "code": dedent(
                '''\
                def transfer(sender_balance, amount, is_frozen):
                    if amount <= 0:
                        return "invalid_amount"
                    if amount > sender_balance:
                        return "insufficient_funds"
                    return sender_balance - amount
                ''')},
        ],
    },
    {
        "slug": "ticket_booking",
        "title": "Event ticket booking",
        "entrypoint": "book_tickets",
        "signature": "book_tickets(available: int, requested: int, max_per_booking: int) -> int | str",
        "params": [
            {"name": "available", "type": "int", "note": "tickets still available"},
            {"name": "requested", "type": "int", "note": "tickets the user wants"},
            {"name": "max_per_booking", "type": "int", "note": "maximum tickets per booking"},
        ],
        "requirement": dedent(
            """\
            As a ticketing system, I want to book seats for an event.

            A booking must be for at least one ticket, no more than the per-booking
            limit, and no more than the tickets still available. On success return how
            many tickets remain; otherwise return "invalid_quantity", "exceeds_limit",
            or "sold_out"."""
        ),
        "canonical_inputs": [
            [100, 4, 6], [100, 0, 6], [100, 7, 6], [100, 6, 6], [3, 5, 10], [3, 3, 10],
        ],
        "reference": dedent(
            '''\
            def book_tickets(available, requested, max_per_booking):
                if requested <= 0:
                    return "invalid_quantity"
                if requested > max_per_booking:
                    return "exceeds_limit"
                if requested > available:
                    return "sold_out"
                return available - requested
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Allows booking zero tickets (checks < 0 instead of <= 0).",
             "code": dedent(
                '''\
                def book_tickets(available, requested, max_per_booking):
                    if requested < 0:
                        return "invalid_quantity"
                    if requested > max_per_booking:
                        return "exceeds_limit"
                    if requested > available:
                        return "sold_out"
                    return available - requested
                ''')},
            {"key": "m2", "description": "Rejects booking exactly the per-booking limit (uses >=).",
             "code": dedent(
                '''\
                def book_tickets(available, requested, max_per_booking):
                    if requested <= 0:
                        return "invalid_quantity"
                    if requested >= max_per_booking:
                        return "exceeds_limit"
                    if requested > available:
                        return "sold_out"
                    return available - requested
                ''')},
            {"key": "m3", "description": "Rejects booking exactly the remaining tickets (uses >=).",
             "code": dedent(
                '''\
                def book_tickets(available, requested, max_per_booking):
                    if requested <= 0:
                        return "invalid_quantity"
                    if requested > max_per_booking:
                        return "exceeds_limit"
                    if requested >= available:
                        return "sold_out"
                    return available - requested
                ''')},
            {"key": "m4", "description": "Skips the per-booking limit check.",
             "code": dedent(
                '''\
                def book_tickets(available, requested, max_per_booking):
                    if requested <= 0:
                        return "invalid_quantity"
                    if requested > available:
                        return "sold_out"
                    return available - requested
                ''')},
        ],
    },
    {
        "slug": "payroll_overtime",
        "title": "Weekly payroll with overtime",
        "entrypoint": "weekly_pay",
        "signature": "weekly_pay(hours: float, hourly_rate: float) -> float",
        "params": [
            {"name": "hours", "type": "float", "note": "hours worked this week"},
            {"name": "hourly_rate", "type": "float", "note": "pay per hour"},
        ],
        "requirement": dedent(
            """\
            As a payroll system, I want to calculate weekly pay including overtime.

            Hours up to 40 are paid at the normal rate. Any hours beyond 40 are
            overtime, paid at 1.5x the normal rate. Negative hours or a negative rate
            are invalid and should return -1. Round the pay to 2 decimals."""
        ),
        "canonical_inputs": [
            [40, 10], [45, 10], [20, 10], [-5, 10], [41, 10], [40, -3],
        ],
        "reference": dedent(
            '''\
            def weekly_pay(hours, hourly_rate):
                if hours < 0 or hourly_rate < 0:
                    return -1.0
                if hours <= 40:
                    return round(hours * hourly_rate, 2)
                overtime = hours - 40
                return round(40 * hourly_rate + overtime * hourly_rate * 1.5, 2)
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Overtime starts after 45 hours, not 40.",
             "code": dedent(
                '''\
                def weekly_pay(hours, hourly_rate):
                    if hours < 0 or hourly_rate < 0:
                        return -1.0
                    if hours <= 45:
                        return round(hours * hourly_rate, 2)
                    overtime = hours - 45
                    return round(45 * hourly_rate + overtime * hourly_rate * 1.5, 2)
                ''')},
            {"key": "m2", "description": "Overtime is paid at 2x instead of 1.5x.",
             "code": dedent(
                '''\
                def weekly_pay(hours, hourly_rate):
                    if hours < 0 or hourly_rate < 0:
                        return -1.0
                    if hours <= 40:
                        return round(hours * hourly_rate, 2)
                    overtime = hours - 40
                    return round(40 * hourly_rate + overtime * hourly_rate * 2.0, 2)
                ''')},
            {"key": "m3", "description": "No check for negative hours or rate.",
             "code": dedent(
                '''\
                def weekly_pay(hours, hourly_rate):
                    if hours <= 40:
                        return round(hours * hourly_rate, 2)
                    overtime = hours - 40
                    return round(40 * hourly_rate + overtime * hourly_rate * 1.5, 2)
                ''')},
            {"key": "m4", "description": "Overtime multiplier applies to ALL hours, not just the extra ones.",
             "code": dedent(
                '''\
                def weekly_pay(hours, hourly_rate):
                    if hours < 0 or hourly_rate < 0:
                        return -1.0
                    if hours <= 40:
                        return round(hours * hourly_rate, 2)
                    return round(hours * hourly_rate * 1.5, 2)
                ''')},
        ],
    },
    {
        "slug": "card_expiry",
        "title": "Credit-card expiry check",
        "entrypoint": "card_not_expired",
        "signature": "card_not_expired(exp_month: int, exp_year: int, cur_month: int, cur_year: int) -> str",
        "params": [
            {"name": "exp_month", "type": "int", "note": "card expiry month, 1-12"},
            {"name": "exp_year", "type": "int", "note": "card expiry year"},
            {"name": "cur_month", "type": "int", "note": "current month"},
            {"name": "cur_year", "type": "int", "note": "current year"},
        ],
        "requirement": dedent(
            """\
            As a payment form, I want to check whether a credit card is still valid.

            A card is valid through the end of its expiry month. If the expiry month is
            not a real month (1-12), it is "invalid". If the expiry date is before the
            current month, it is "expired". Otherwise it is "valid"."""
        ),
        "canonical_inputs": [
            [6, 2027, 8, 2026], [8, 2026, 8, 2026], [7, 2026, 8, 2026],
            [6, 2025, 8, 2026], [13, 2027, 8, 2026], [0, 2027, 8, 2026],
        ],
        "reference": dedent(
            '''\
            def card_not_expired(exp_month, exp_year, cur_month, cur_year):
                if exp_month < 1 or exp_month > 12:
                    return "invalid"
                if exp_year < cur_year:
                    return "expired"
                if exp_year == cur_year and exp_month < cur_month:
                    return "expired"
                return "valid"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Only checks the low end of the month, so month 13 is accepted.",
             "code": dedent(
                '''\
                def card_not_expired(exp_month, exp_year, cur_month, cur_year):
                    if exp_month < 1:
                        return "invalid"
                    if exp_year < cur_year:
                        return "expired"
                    if exp_year == cur_year and exp_month < cur_month:
                        return "expired"
                    return "valid"
                ''')},
            {"key": "m2", "description": "Treats a card expiring this year as already expired (uses <=).",
             "code": dedent(
                '''\
                def card_not_expired(exp_month, exp_year, cur_month, cur_year):
                    if exp_month < 1 or exp_month > 12:
                        return "invalid"
                    if exp_year <= cur_year:
                        return "expired"
                    if exp_year == cur_year and exp_month < cur_month:
                        return "expired"
                    return "valid"
                ''')},
            {"key": "m3", "description": "Expires a card during its own expiry month (uses <=).",
             "code": dedent(
                '''\
                def card_not_expired(exp_month, exp_year, cur_month, cur_year):
                    if exp_month < 1 or exp_month > 12:
                        return "invalid"
                    if exp_year < cur_year:
                        return "expired"
                    if exp_year == cur_year and exp_month <= cur_month:
                        return "expired"
                    return "valid"
                ''')},
            {"key": "m4", "description": "Ignores the month when the years match, so an earlier month this year still passes.",
             "code": dedent(
                '''\
                def card_not_expired(exp_month, exp_year, cur_month, cur_year):
                    if exp_month < 1 or exp_month > 12:
                        return "invalid"
                    if exp_year < cur_year:
                        return "expired"
                    return "valid"
                ''')},
        ],
    },
    {
        "slug": "shipping_fee",
        "title": "Parcel shipping fee",
        "entrypoint": "shipping_fee",
        "signature": "shipping_fee(weight_kg: float, distance_km: int, is_express: bool) -> float",
        "params": [
            {"name": "weight_kg", "type": "float", "note": "parcel weight in kg"},
            {"name": "distance_km", "type": "int", "note": "shipping distance in km"},
            {"name": "is_express", "type": "bool", "note": "whether express delivery was chosen"},
        ],
        "requirement": dedent(
            """\
            As a shipping calculator, I want to price a parcel delivery.

            The fee is a $5 base, plus $2 per kg, plus $1 for every full 100 km of
            distance. Express delivery doubles the whole fee. A parcel must weigh more
            than 0 and at most 30 kg, otherwise return -1 for an invalid parcel. Round
            the fee to 2 decimals."""
        ),
        "canonical_inputs": [
            [10, 250, False], [30, 100, False], [0, 100, False],
            [10, 100, True], [10, 150, False], [31, 100, False],
        ],
        "reference": dedent(
            '''\
            def shipping_fee(weight_kg, distance_km, is_express):
                if weight_kg <= 0 or weight_kg > 30:
                    return -1.0
                fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 100)
                if is_express:
                    fee = fee * 2
                return round(fee, 2)
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Rejects a parcel of exactly 30 kg (uses >= instead of >).",
             "code": dedent(
                '''\
                def shipping_fee(weight_kg, distance_km, is_express):
                    if weight_kg <= 0 or weight_kg >= 30:
                        return -1.0
                    fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 100)
                    if is_express:
                        fee = fee * 2
                    return round(fee, 2)
                ''')},
            {"key": "m2", "description": "Allows a zero-weight parcel (uses < 0 instead of <= 0).",
             "code": dedent(
                '''\
                def shipping_fee(weight_kg, distance_km, is_express):
                    if weight_kg < 0 or weight_kg > 30:
                        return -1.0
                    fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 100)
                    if is_express:
                        fee = fee * 2
                    return round(fee, 2)
                ''')},
            {"key": "m3", "description": "Forgets to double the fee for express delivery.",
             "code": dedent(
                '''\
                def shipping_fee(weight_kg, distance_km, is_express):
                    if weight_kg <= 0 or weight_kg > 30:
                        return -1.0
                    fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 100)
                    return round(fee, 2)
                ''')},
            {"key": "m4", "description": "Charges per 200 km instead of per 100 km.",
             "code": dedent(
                '''\
                def shipping_fee(weight_kg, distance_km, is_express):
                    if weight_kg <= 0 or weight_kg > 30:
                        return -1.0
                    fee = 5.0 + 2.0 * weight_kg + 1.0 * (distance_km // 200)
                    if is_express:
                        fee = fee * 2
                    return round(fee, 2)
                ''')},
        ],
    },
    {
        "slug": "loan_approval",
        "title": "Loan application decision",
        "entrypoint": "loan_approval",
        "signature": "loan_approval(credit_score: int, annual_income: int, loan_amount: int) -> str",
        "params": [
            {"name": "credit_score", "type": "int", "note": "applicant credit score"},
            {"name": "annual_income", "type": "int", "note": "applicant yearly income"},
            {"name": "loan_amount", "type": "int", "note": "amount requested"},
        ],
        "requirement": dedent(
            """\
            As a lending system, I want to decide a loan application.

            Anyone with a credit score below 600 is declined. A loan larger than five
            times the applicant's yearly income is also declined. A score of 750 or
            above is approved automatically; everyone else in between is sent for manual
            review. Return "denied", "approved", or "refer"."""
        ),
        "canonical_inputs": [
            [800, 10000, 20000], [600, 10000, 20000], [750, 10000, 20000],
            [800, 10000, 40000], [800, 10000, 60000], [550, 10000, 20000],
        ],
        "reference": dedent(
            '''\
            def loan_approval(credit_score, annual_income, loan_amount):
                if credit_score < 600:
                    return "denied"
                if loan_amount > 5 * annual_income:
                    return "denied"
                if credit_score >= 750:
                    return "approved"
                return "refer"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Declines a score of exactly 600 (uses <= instead of <).",
             "code": dedent(
                '''\
                def loan_approval(credit_score, annual_income, loan_amount):
                    if credit_score <= 600:
                        return "denied"
                    if loan_amount > 5 * annual_income:
                        return "denied"
                    if credit_score >= 750:
                        return "approved"
                    return "refer"
                ''')},
            {"key": "m2", "description": "Requires a score above 750 to auto-approve (uses > instead of >=).",
             "code": dedent(
                '''\
                def loan_approval(credit_score, annual_income, loan_amount):
                    if credit_score < 600:
                        return "denied"
                    if loan_amount > 5 * annual_income:
                        return "denied"
                    if credit_score > 750:
                        return "approved"
                    return "refer"
                ''')},
            {"key": "m3", "description": "Caps the loan at 3x income instead of 5x.",
             "code": dedent(
                '''\
                def loan_approval(credit_score, annual_income, loan_amount):
                    if credit_score < 600:
                        return "denied"
                    if loan_amount > 3 * annual_income:
                        return "denied"
                    if credit_score >= 750:
                        return "approved"
                    return "refer"
                ''')},
            {"key": "m4", "description": "Skips the loan-to-income check entirely.",
             "code": dedent(
                '''\
                def loan_approval(credit_score, annual_income, loan_amount):
                    if credit_score < 600:
                        return "denied"
                    if credit_score >= 750:
                        return "approved"
                    return "refer"
                ''')},
        ],
    },
    {
        "slug": "grade_letter",
        "title": "Exam grade letter",
        "entrypoint": "grade_letter",
        "signature": "grade_letter(score: int) -> str",
        "params": [
            {"name": "score", "type": "int", "note": "exam score, 0-100"},
        ],
        "requirement": dedent(
            """\
            As a grading tool, I want to turn an exam score into a letter grade.

            90 and above is an A, the 80s a B, the 70s a C, the 60s a D, and anything
            below 60 is an F. A score outside 0-100 is not a real score and should
            return "invalid"."""
        ),
        "canonical_inputs": [
            [90], [60], [82], [150], [-5], [75],
        ],
        "reference": dedent(
            '''\
            def grade_letter(score):
                if score < 0 or score > 100:
                    return "invalid"
                if score >= 90:
                    return "A"
                if score >= 80:
                    return "B"
                if score >= 70:
                    return "C"
                if score >= 60:
                    return "D"
                return "F"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "A 90 falls short of an A (uses > instead of >=).",
             "code": dedent(
                '''\
                def grade_letter(score):
                    if score < 0 or score > 100:
                        return "invalid"
                    if score > 90:
                        return "A"
                    if score >= 80:
                        return "B"
                    if score >= 70:
                        return "C"
                    if score >= 60:
                        return "D"
                    return "F"
                ''')},
            {"key": "m2", "description": "A 60 falls short of a D (uses > instead of >=).",
             "code": dedent(
                '''\
                def grade_letter(score):
                    if score < 0 or score > 100:
                        return "invalid"
                    if score >= 90:
                        return "A"
                    if score >= 80:
                        return "B"
                    if score >= 70:
                        return "C"
                    if score > 60:
                        return "D"
                    return "F"
                ''')},
            {"key": "m3", "description": "The B cutoff is 85 instead of 80.",
             "code": dedent(
                '''\
                def grade_letter(score):
                    if score < 0 or score > 100:
                        return "invalid"
                    if score >= 90:
                        return "A"
                    if score >= 85:
                        return "B"
                    if score >= 70:
                        return "C"
                    if score >= 60:
                        return "D"
                    return "F"
                ''')},
            {"key": "m4", "description": "Never rejects a score above 100.",
             "code": dedent(
                '''\
                def grade_letter(score):
                    if score < 0:
                        return "invalid"
                    if score >= 90:
                        return "A"
                    if score >= 80:
                        return "B"
                    if score >= 70:
                        return "C"
                    if score >= 60:
                        return "D"
                    return "F"
                ''')},
        ],
    },
    {
        "slug": "parking_fee",
        "title": "Car park pricing",
        "entrypoint": "parking_fee",
        "signature": "parking_fee(minutes: int) -> int",
        "params": [
            {"name": "minutes", "type": "int", "note": "minutes parked"},
        ],
        "requirement": dedent(
            """\
            As a car park, I want to price a stay by the minute.

            The first 30 minutes are free. After that the charge is $3 for every hour
            or part of an hour of the whole stay. A negative duration is invalid and
            returns -1."""
        ),
        "canonical_inputs": [
            [10], [30], [45], [120], [-10], [90],
        ],
        "reference": dedent(
            '''\
            def parking_fee(minutes):
                if minutes < 0:
                    return -1
                if minutes <= 30:
                    return 0
                hours = (minutes + 59) // 60
                return 3 * hours
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Charges for exactly 30 minutes (uses < instead of <=).",
             "code": dedent(
                '''\
                def parking_fee(minutes):
                    if minutes < 0:
                        return -1
                    if minutes < 30:
                        return 0
                    hours = (minutes + 59) // 60
                    return 3 * hours
                ''')},
            {"key": "m2", "description": "Adds the hours to $3 instead of multiplying.",
             "code": dedent(
                '''\
                def parking_fee(minutes):
                    if minutes < 0:
                        return -1
                    if minutes <= 30:
                        return 0
                    hours = (minutes + 59) // 60
                    return 3 + hours
                ''')},
            {"key": "m3", "description": "Gives a 60-minute free period instead of 30.",
             "code": dedent(
                '''\
                def parking_fee(minutes):
                    if minutes < 0:
                        return -1
                    if minutes <= 60:
                        return 0
                    hours = (minutes + 59) // 60
                    return 3 * hours
                ''')},
            {"key": "m4", "description": "Never rejects a negative duration.",
             "code": dedent(
                '''\
                def parking_fee(minutes):
                    if minutes <= 30:
                        return 0
                    hours = (minutes + 59) // 60
                    return 3 * hours
                ''')},
        ],
    },
    {
        "slug": "bmi_category",
        "title": "BMI health category",
        "entrypoint": "bmi_category",
        "signature": "bmi_category(weight_kg: float, height_m: float) -> str",
        "params": [
            {"name": "weight_kg", "type": "float", "note": "body weight in kg"},
            {"name": "height_m", "type": "float", "note": "height in metres"},
        ],
        "requirement": dedent(
            """\
            As a health tool, I want to classify a body-mass index.

            BMI is weight divided by height squared. Below 18.5 is "underweight", below
            25 is "normal", below 30 is "overweight", and 30 or more is "obese". A
            weight or height that is zero or negative is invalid and returns
            "invalid"."""
        ),
        "canonical_inputs": [
            [100, 2], [74, 2], [45, 1.5], [0, 2], [70, 1.75], [60, -1],
        ],
        "reference": dedent(
            '''\
            def bmi_category(weight_kg, height_m):
                if weight_kg <= 0 or height_m <= 0:
                    return "invalid"
                bmi = weight_kg / (height_m * height_m)
                if bmi < 18.5:
                    return "underweight"
                if bmi < 25:
                    return "normal"
                if bmi < 30:
                    return "overweight"
                return "obese"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "A BMI of exactly 25 counts as normal (uses <= instead of <).",
             "code": dedent(
                '''\
                def bmi_category(weight_kg, height_m):
                    if weight_kg <= 0 or height_m <= 0:
                        return "invalid"
                    bmi = weight_kg / (height_m * height_m)
                    if bmi < 18.5:
                        return "underweight"
                    if bmi <= 25:
                        return "normal"
                    if bmi < 30:
                        return "overweight"
                    return "obese"
                ''')},
            {"key": "m2", "description": "A BMI of exactly 18.5 counts as underweight (uses <=).",
             "code": dedent(
                '''\
                def bmi_category(weight_kg, height_m):
                    if weight_kg <= 0 or height_m <= 0:
                        return "invalid"
                    bmi = weight_kg / (height_m * height_m)
                    if bmi <= 18.5:
                        return "underweight"
                    if bmi < 25:
                        return "normal"
                    if bmi < 30:
                        return "overweight"
                    return "obese"
                ''')},
            {"key": "m3", "description": "Adds the height to itself instead of squaring it.",
             "code": dedent(
                '''\
                def bmi_category(weight_kg, height_m):
                    if weight_kg <= 0 or height_m <= 0:
                        return "invalid"
                    bmi = weight_kg / (height_m + height_m)
                    if bmi < 18.5:
                        return "underweight"
                    if bmi < 25:
                        return "normal"
                    if bmi < 30:
                        return "overweight"
                    return "obese"
                ''')},
            {"key": "m4", "description": "Ignores a zero or negative weight.",
             "code": dedent(
                '''\
                def bmi_category(weight_kg, height_m):
                    if height_m <= 0:
                        return "invalid"
                    bmi = weight_kg / (height_m * height_m)
                    if bmi < 18.5:
                        return "underweight"
                    if bmi < 25:
                        return "normal"
                    if bmi < 30:
                        return "overweight"
                    return "obese"
                ''')},
        ],
    },
    {
        "slug": "refund_eligibility",
        "title": "Purchase refund eligibility",
        "entrypoint": "refund_eligibility",
        "signature": "refund_eligibility(days_since_purchase: int, is_opened: bool, price: int) -> str",
        "params": [
            {"name": "days_since_purchase", "type": "int", "note": "days since the purchase"},
            {"name": "is_opened", "type": "bool", "note": "whether the item was opened"},
            {"name": "price", "type": "int", "note": "item price"},
        ],
        "requirement": dedent(
            """\
            As a returns desk, I want to decide whether a purchase can be refunded.

            Refunds are only allowed within 30 days of purchase, otherwise the request
            has "expired". An opened item can still be refunded, but only if it cost at
            least $50; an opened item under $50 is "denied". Anything else is
            "approved"."""
        ),
        "canonical_inputs": [
            [10, True, 100], [30, False, 100], [10, True, 60],
            [10, False, 20], [10, True, 20], [40, False, 100],
        ],
        "reference": dedent(
            '''\
            def refund_eligibility(days_since_purchase, is_opened, price):
                if days_since_purchase > 30:
                    return "expired"
                if is_opened and price < 50:
                    return "denied"
                return "approved"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Expires a refund on day 30 exactly (uses >= instead of >).",
             "code": dedent(
                '''\
                def refund_eligibility(days_since_purchase, is_opened, price):
                    if days_since_purchase >= 30:
                        return "expired"
                    if is_opened and price < 50:
                        return "denied"
                    return "approved"
                ''')},
            {"key": "m2", "description": "Uses a $100 restocking threshold instead of $50.",
             "code": dedent(
                '''\
                def refund_eligibility(days_since_purchase, is_opened, price):
                    if days_since_purchase > 30:
                        return "expired"
                    if is_opened and price < 100:
                        return "denied"
                    return "approved"
                ''')},
            {"key": "m3", "description": "Denies on opened OR cheap, instead of opened AND cheap.",
             "code": dedent(
                '''\
                def refund_eligibility(days_since_purchase, is_opened, price):
                    if days_since_purchase > 30:
                        return "expired"
                    if is_opened or price < 50:
                        return "denied"
                    return "approved"
                ''')},
            {"key": "m4", "description": "Skips the opened-item restocking rule.",
             "code": dedent(
                '''\
                def refund_eligibility(days_since_purchase, is_opened, price):
                    if days_since_purchase > 30:
                        return "expired"
                    return "approved"
                ''')},
        ],
    },
    {
        "slug": "speeding_fine",
        "title": "Speeding fine tiers",
        "entrypoint": "speeding_fine",
        "signature": "speeding_fine(speed: int, limit: int) -> int",
        "params": [
            {"name": "speed", "type": "int", "note": "measured speed"},
            {"name": "limit", "type": "int", "note": "posted speed limit"},
        ],
        "requirement": dedent(
            """\
            As a traffic system, I want to work out a speeding fine.

            Driving at or below the limit is no fine. Up to 10 over the limit is a $50
            fine, up to 30 over is $150, and more than 30 over is $300. A speed or limit
            that is zero or negative is invalid and returns -1."""
        ),
        "canonical_inputs": [
            [70, 60], [80, 60], [0, 60], [50, 60], [100, 60], [65, 60],
        ],
        "reference": dedent(
            '''\
            def speeding_fine(speed, limit):
                if speed <= 0 or limit <= 0:
                    return -1
                over = speed - limit
                if over <= 0:
                    return 0
                if over <= 10:
                    return 50
                if over <= 30:
                    return 150
                return 300
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Being exactly 10 over lands in the higher tier (uses < instead of <=).",
             "code": dedent(
                '''\
                def speeding_fine(speed, limit):
                    if speed <= 0 or limit <= 0:
                        return -1
                    over = speed - limit
                    if over <= 0:
                        return 0
                    if over < 10:
                        return 50
                    if over <= 30:
                        return 150
                    return 300
                ''')},
            {"key": "m2", "description": "The middle fine is $100 instead of $150.",
             "code": dedent(
                '''\
                def speeding_fine(speed, limit):
                    if speed <= 0 or limit <= 0:
                        return -1
                    over = speed - limit
                    if over <= 0:
                        return 0
                    if over <= 10:
                        return 50
                    if over <= 30:
                        return 100
                    return 300
                ''')},
            {"key": "m3", "description": "Skips the invalid speed/limit check.",
             "code": dedent(
                '''\
                def speeding_fine(speed, limit):
                    over = speed - limit
                    if over <= 0:
                        return 0
                    if over <= 10:
                        return 50
                    if over <= 30:
                        return 150
                    return 300
                ''')},
            {"key": "m4", "description": "Adds speed and limit instead of subtracting.",
             "code": dedent(
                '''\
                def speeding_fine(speed, limit):
                    if speed <= 0 or limit <= 0:
                        return -1
                    over = speed + limit
                    if over <= 0:
                        return 0
                    if over <= 10:
                        return 50
                    if over <= 30:
                        return 150
                    return 300
                ''')},
        ],
    },
    {
        "slug": "leap_year",
        "title": "Leap-year check",
        "entrypoint": "leap_year",
        "signature": "leap_year(year: int) -> str",
        "params": [
            {"name": "year", "type": "int", "note": "the year to test"},
        ],
        "requirement": dedent(
            """\
            As a calendar utility, I want to tell whether a year is a leap year.

            A year is a leap year if it is divisible by 4, except that century years are
            not leap years unless they are also divisible by 400. A year of zero or less
            is invalid. Return "leap", "common", or "invalid"."""
        ),
        "canonical_inputs": [
            [2000], [2004], [0], [1900], [2001], [2100],
        ],
        "reference": dedent(
            '''\
            def leap_year(year):
                if year <= 0:
                    return "invalid"
                if year % 400 == 0:
                    return "leap"
                if year % 100 == 0:
                    return "common"
                if year % 4 == 0:
                    return "leap"
                return "common"
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Drops the divisible-by-400 exception, so 2000 looks common.",
             "code": dedent(
                '''\
                def leap_year(year):
                    if year <= 0:
                        return "invalid"
                    if year % 100 == 0:
                        return "common"
                    if year % 4 == 0:
                        return "leap"
                    return "common"
                ''')},
            {"key": "m2", "description": "Tests divisibility by 5 instead of 4.",
             "code": dedent(
                '''\
                def leap_year(year):
                    if year <= 0:
                        return "invalid"
                    if year % 400 == 0:
                        return "leap"
                    if year % 100 == 0:
                        return "common"
                    if year % 5 == 0:
                        return "leap"
                    return "common"
                ''')},
            {"key": "m3", "description": "Treats year 0 as valid (uses < instead of <=).",
             "code": dedent(
                '''\
                def leap_year(year):
                    if year < 0:
                        return "invalid"
                    if year % 400 == 0:
                        return "leap"
                    if year % 100 == 0:
                        return "common"
                    if year % 4 == 0:
                        return "leap"
                    return "common"
                ''')},
            {"key": "m4", "description": "Flips the century test, so ordinary century rules invert.",
             "code": dedent(
                '''\
                def leap_year(year):
                    if year <= 0:
                        return "invalid"
                    if year % 400 == 0:
                        return "leap"
                    if year % 100 != 0:
                        return "common"
                    if year % 4 == 0:
                        return "leap"
                    return "common"
                ''')},
        ],
    },
]


# ---------------------------------------------------------------------------
# Fault taxonomy
#
# Every seeded bug is labelled with the *kind* of mistake it represents, drawn
# from the classic mutation-operator families but named in plain language. This
# is what lets the evaluation report fault detection *by fault class* — e.g.
# "the multi-agent suite catches boundary bugs the baseline misses" — instead of
# a single undifferentiated number. It turns the benchmark into a categorised,
# reusable artifact rather than an opaque bag of bugs.
# ---------------------------------------------------------------------------

# Ordered so the dashboard can render a stable legend.
FAULT_TAXONOMY: list[dict] = [
    {"key": "boundary", "label": "Boundary",
     "blurb": "An off-by-one at a threshold — a < written as <=, a > as >=."},
    {"key": "wrong_constant", "label": "Wrong value",
     "blurb": "A literal threshold, factor, or result changed to the wrong number."},
    {"key": "wrong_operator", "label": "Wrong operator",
     "blurb": "An arithmetic or logical operator swapped — + for -, and for or."},
    {"key": "missing_condition", "label": "Missing check",
     "blurb": "A whole guard, branch, or clause dropped from the logic."},
    {"key": "control_flow", "label": "Control flow",
     "blurb": "Guards evaluated in the wrong order, so the wrong rule wins."},
]

FAULT_TYPE_KEYS = {f["key"] for f in FAULT_TAXONOMY}
FAULT_TYPE_LABELS = {f["key"]: f["label"] for f in FAULT_TAXONOMY}

# (slug -> mutant key -> fault class). Kept beside the corpus rather than inline
# in each mutant dict so the large, verbatim code blocks above stay untouched and
# easy to diff. `seed.py` stamps these onto the BenchmarkMutant rows.
FAULT_TYPES: dict[str, dict[str, str]] = {
    "atm_withdrawal": {"m1": "boundary", "m2": "boundary", "m3": "boundary", "m4": "missing_condition"},
    "login_lockout": {"m1": "control_flow", "m2": "boundary", "m3": "wrong_constant", "m4": "missing_condition"},
    "signup_validation": {"m1": "boundary", "m2": "boundary", "m3": "missing_condition", "m4": "missing_condition"},
    "discount_pricing": {"m1": "missing_condition", "m2": "missing_condition", "m3": "wrong_operator", "m4": "missing_condition"},
    "bank_transfer": {"m1": "control_flow", "m2": "boundary", "m3": "boundary", "m4": "missing_condition"},
    "ticket_booking": {"m1": "boundary", "m2": "boundary", "m3": "boundary", "m4": "missing_condition"},
    "payroll_overtime": {"m1": "wrong_constant", "m2": "wrong_constant", "m3": "missing_condition", "m4": "wrong_operator"},
    "card_expiry": {"m1": "missing_condition", "m2": "boundary", "m3": "boundary", "m4": "missing_condition"},
    "shipping_fee": {"m1": "boundary", "m2": "boundary", "m3": "missing_condition", "m4": "wrong_constant"},
    "loan_approval": {"m1": "boundary", "m2": "boundary", "m3": "wrong_constant", "m4": "missing_condition"},
    "grade_letter": {"m1": "boundary", "m2": "boundary", "m3": "wrong_constant", "m4": "missing_condition"},
    "parking_fee": {"m1": "boundary", "m2": "wrong_operator", "m3": "wrong_constant", "m4": "missing_condition"},
    "bmi_category": {"m1": "boundary", "m2": "boundary", "m3": "wrong_operator", "m4": "missing_condition"},
    "refund_eligibility": {"m1": "boundary", "m2": "wrong_constant", "m3": "wrong_operator", "m4": "missing_condition"},
    "speeding_fine": {"m1": "boundary", "m2": "wrong_constant", "m3": "missing_condition", "m4": "wrong_operator"},
    "leap_year": {"m1": "missing_condition", "m2": "wrong_constant", "m3": "boundary", "m4": "wrong_operator"},
}


def fault_type_for(slug: str, mutant_key: str) -> str | None:
    """The fault class for one seeded bug, or None if unclassified."""
    return FAULT_TYPES.get(slug, {}).get(mutant_key)


def _manifest_view() -> list[dict]:
    """Metadata-only view of the corpus (no code bodies) for manifest.json."""
    return [
        {
            "slug": p["slug"],
            "title": p["title"],
            "entrypoint": p["entrypoint"],
            "signature": p["signature"],
            "params": p["params"],
            "requirement": p["requirement"],
            "canonical_inputs": p["canonical_inputs"],
            "reference_file": f"fixtures/{p['slug']}/reference.py",
            "mutants": [
                {
                    "key": m["key"],
                    "description": m["description"],
                    "fault_type": fault_type_for(p["slug"], m["key"]),
                    "file": f"fixtures/{p['slug']}/mutants/{m['key']}.py",
                }
                for m in p["mutants"]
            ],
        }
        for p in PROGRAMS
    ]


def build_fixtures(base_dir: str | Path | None = None) -> Path:
    """Materialize the corpus to a reviewable on-disk layout:
    `fixtures/<slug>/reference.py`, `fixtures/<slug>/mutants/<key>.py`, and
    `manifest.json`. The runtime does not depend on these; they exist so the
    corpus can be inspected and cited in the thesis appendix. Returns the base
    directory written to."""
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    for p in PROGRAMS:
        item_dir = base / "fixtures" / p["slug"]
        (item_dir / "mutants").mkdir(parents=True, exist_ok=True)
        (item_dir / "reference.py").write_text(p["reference"], encoding="utf-8")
        for m in p["mutants"]:
            (item_dir / "mutants" / f"{m['key']}.py").write_text(
                m["code"], encoding="utf-8"
            )
    (base / "manifest.json").write_text(
        json.dumps(_manifest_view(), indent=2) + "\n", encoding="utf-8"
    )
    return base


if __name__ == "__main__":
    out = build_fixtures()
    print(f"Wrote {len(PROGRAMS)} benchmark items + manifest to {out}")
