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
]


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
