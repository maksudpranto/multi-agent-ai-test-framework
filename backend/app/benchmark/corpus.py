"""The executable micro-benchmark corpus (authoritative source).

Each entry is a small, pure Python function with:
  - a natural-language `requirement` the pipeline generates tests from,
  - an `entrypoint` + `signature` the fault-detection harness calls,
  - a correct `reference` implementation that acts as the test ORACLE,
  - `canonical_inputs`: deterministic fallback argument lists, and
  - three `mutants`: the reference with one deliberate, subtle bug seeded in.

The thesis claim rests on this file: we do not ask an LLM whether a suite is
good — we harvest the concrete inputs the suite implies, run every mutant on
them, and count how many diverge from the reference (are "killed"). A stronger
suite (more boundary/negative inputs) kills more mutants. Some mutants are
killed only by a boundary input a weak suite omits — that spread is what lets
the multi-agent pipeline out-score the single-LLM baseline.

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
        "slug": "bmi_calculator",
        "title": "BMI category classifier",
        "entrypoint": "bmi_category",
        "signature": "bmi_category(weight_kg: float, height_m: float) -> str",
        "params": [
            {"name": "weight_kg", "type": "float", "note": "body weight in kilograms, > 0"},
            {"name": "height_m", "type": "float", "note": "height in metres, > 0"},
        ],
        "requirement": dedent(
            """\
            As a health-app user, I want to enter my weight and height so the app
            tells me my BMI category.

            BMI is weight_kg divided by height_m squared. The category is decided by
            standard WHO cut-offs applied to the BMI value:
              - below 18.5           -> "underweight"
              - 18.5 up to below 25  -> "normal"
              - 25 up to below 30    -> "overweight"
              - 30 and above         -> "obese"

            The 18.5, 25 and 30 boundaries are inclusive on the lower side of each
            band, so a value of exactly 25 is "overweight", not "normal"."""
        ),
        "canonical_inputs": [[50, 1.7], [68, 1.7], [72.5, 1.72], [80, 1.7], [100, 1.7]],
        "reference": dedent(
            '''\
            def bmi_category(weight_kg, height_m):
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
            {
                "key": "m1",
                "description": "Normal/overweight boundary moved from 25 to 24 (off-by-one on the threshold).",
                "code": dedent(
                    '''\
                    def bmi_category(weight_kg, height_m):
                        bmi = weight_kg / (height_m * height_m)
                        if bmi < 18.5:
                            return "underweight"
                        if bmi < 24:
                            return "normal"
                        if bmi < 30:
                            return "overweight"
                        return "obese"
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "BMI formula missing the square on height (divides by height, not height^2).",
                "code": dedent(
                    '''\
                    def bmi_category(weight_kg, height_m):
                        bmi = weight_kg / height_m
                        if bmi < 18.5:
                            return "underweight"
                        if bmi < 25:
                            return "normal"
                        if bmi < 30:
                            return "overweight"
                        return "obese"
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Underweight band mislabelled as 'normal'.",
                "code": dedent(
                    '''\
                    def bmi_category(weight_kg, height_m):
                        bmi = weight_kg / (height_m * height_m)
                        if bmi < 18.5:
                            return "normal"
                        if bmi < 25:
                            return "normal"
                        if bmi < 30:
                            return "overweight"
                        return "obese"
                    '''
                ),
            },
        ],
    },
    {
        "slug": "fizzbuzz",
        "title": "FizzBuzz",
        "entrypoint": "fizzbuzz",
        "signature": "fizzbuzz(n: int) -> str",
        "params": [{"name": "n", "type": "int", "note": "a positive integer"}],
        "requirement": dedent(
            """\
            As a developer, I want a fizzbuzz(n) function that returns a string for a
            single number n.

            Rules, applied in order:
              - if n is divisible by both 3 and 5, return "FizzBuzz"
              - else if n is divisible by 3, return "Fizz"
              - else if n is divisible by 5, return "Buzz"
              - otherwise return the number itself as a string, e.g. "7"

            The result is always a string, even in the plain-number case."""
        ),
        "canonical_inputs": [[1], [3], [5], [15], [7]],
        "reference": dedent(
            '''\
            def fizzbuzz(n):
                if n % 15 == 0:
                    return "FizzBuzz"
                if n % 3 == 0:
                    return "Fizz"
                if n % 5 == 0:
                    return "Buzz"
                return str(n)
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "FizzBuzz check uses 30 instead of 15, so 15 yields 'Fizz'.",
                "code": dedent(
                    '''\
                    def fizzbuzz(n):
                        if n % 30 == 0:
                            return "FizzBuzz"
                        if n % 3 == 0:
                            return "Fizz"
                        if n % 5 == 0:
                            return "Buzz"
                        return str(n)
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "Fizz and Buzz swapped.",
                "code": dedent(
                    '''\
                    def fizzbuzz(n):
                        if n % 15 == 0:
                            return "FizzBuzz"
                        if n % 3 == 0:
                            return "Buzz"
                        if n % 5 == 0:
                            return "Fizz"
                        return str(n)
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Plain-number case returns an int, not a string.",
                "code": dedent(
                    '''\
                    def fizzbuzz(n):
                        if n % 15 == 0:
                            return "FizzBuzz"
                        if n % 3 == 0:
                            return "Fizz"
                        if n % 5 == 0:
                            return "Buzz"
                        return n
                    '''
                ),
            },
        ],
    },
    {
        "slug": "password_validator",
        "title": "Password strength validator",
        "entrypoint": "is_valid_password",
        "signature": "is_valid_password(password: str) -> bool",
        "params": [{"name": "password", "type": "str", "note": "the candidate password"}],
        "requirement": dedent(
            """\
            As a user signing up, I want my password checked so weak ones are rejected.

            is_valid_password(password) returns True only if ALL of these hold:
              - it is at least 8 characters long
              - it contains at least one digit
              - it contains at least one uppercase letter
              - it contains at least one lowercase letter

            If any rule fails, return False. A 7-character password must be rejected;
            an 8-character one that meets the other rules is accepted."""
        ),
        "canonical_inputs": [
            ["Abcdefg1"],
            ["Short1A"],
            ["alllower1"],
            ["ALLUPPER1"],
            ["NoDigitsAbc"],
        ],
        "reference": dedent(
            '''\
            def is_valid_password(password):
                if len(password) < 8:
                    return False
                if not any(c.isdigit() for c in password):
                    return False
                if not any(c.isupper() for c in password):
                    return False
                if not any(c.islower() for c in password):
                    return False
                return True
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "Length check off-by-one: accepts 7-character passwords.",
                "code": dedent(
                    '''\
                    def is_valid_password(password):
                        if len(password) < 7:
                            return False
                        if not any(c.isdigit() for c in password):
                            return False
                        if not any(c.isupper() for c in password):
                            return False
                        if not any(c.islower() for c in password):
                            return False
                        return True
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "Digit requirement dropped.",
                "code": dedent(
                    '''\
                    def is_valid_password(password):
                        if len(password) < 8:
                            return False
                        if not any(c.isupper() for c in password):
                            return False
                        if not any(c.islower() for c in password):
                            return False
                        return True
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Lowercase requirement dropped.",
                "code": dedent(
                    '''\
                    def is_valid_password(password):
                        if len(password) < 8:
                            return False
                        if not any(c.isdigit() for c in password):
                            return False
                        if not any(c.isupper() for c in password):
                            return False
                        return True
                    '''
                ),
            },
        ],
    },
    {
        "slug": "leap_year",
        "title": "Leap-year check",
        "entrypoint": "is_leap_year",
        "signature": "is_leap_year(year: int) -> bool",
        "params": [{"name": "year", "type": "int", "note": "a Gregorian calendar year"}],
        "requirement": dedent(
            """\
            As a calendar feature, I want is_leap_year(year) to tell me whether a year
            is a leap year under the Gregorian rules:
              - divisible by 400            -> leap (e.g. 2000)
              - else divisible by 100       -> not leap (e.g. 1900)
              - else divisible by 4         -> leap (e.g. 2024)
              - otherwise                   -> not leap (e.g. 2023)

            The century rule (1900 is NOT a leap year) and its 400-year exception
            (2000 IS) are the cases that catch naive implementations."""
        ),
        "canonical_inputs": [[2000], [1900], [2024], [2023], [2400]],
        "reference": dedent(
            '''\
            def is_leap_year(year):
                if year % 400 == 0:
                    return True
                if year % 100 == 0:
                    return False
                return year % 4 == 0
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "Missing the 400-year exception, so 2000 is wrongly not-leap.",
                "code": dedent(
                    '''\
                    def is_leap_year(year):
                        if year % 100 == 0:
                            return False
                        return year % 4 == 0
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "Divisibility-by-4 test corrupted to '% 4 == 1'.",
                "code": dedent(
                    '''\
                    def is_leap_year(year):
                        if year % 400 == 0:
                            return True
                        if year % 100 == 0:
                            return False
                        return year % 4 == 1
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Century rule inverted, so 1900 is wrongly leap.",
                "code": dedent(
                    '''\
                    def is_leap_year(year):
                        if year % 400 == 0:
                            return True
                        if year % 100 == 0:
                            return True
                        return year % 4 == 0
                    '''
                ),
            },
        ],
    },
    {
        "slug": "grade_calculator",
        "title": "Letter-grade calculator",
        "entrypoint": "letter_grade",
        "signature": "letter_grade(score: int) -> str",
        "params": [{"name": "score", "type": "int", "note": "an exam score, 0-100"}],
        "requirement": dedent(
            """\
            As a teacher, I want letter_grade(score) to convert a 0-100 score into a
            letter using these inclusive cut-offs:
              - 90 and above -> "A"
              - 80 to 89     -> "B"
              - 70 to 79     -> "C"
              - 60 to 69     -> "D"
              - below 60     -> "F"

            The boundaries are inclusive: a score of exactly 90 is an "A", exactly 80
            is a "B", and so on."""
        ),
        "canonical_inputs": [[95], [89], [85], [72], [50]],
        "reference": dedent(
            '''\
            def letter_grade(score):
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
            {
                "key": "m1",
                "description": "A cut-off moved to 89, so 89 wrongly scores an 'A'.",
                "code": dedent(
                    '''\
                    def letter_grade(score):
                        if score >= 89:
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
            },
            {
                "key": "m2",
                "description": "Failing grade returns 'E' instead of 'F'.",
                "code": dedent(
                    '''\
                    def letter_grade(score):
                        if score >= 90:
                            return "A"
                        if score >= 80:
                            return "B"
                        if score >= 70:
                            return "C"
                        if score >= 60:
                            return "D"
                        return "E"
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "B and C bands swapped.",
                "code": dedent(
                    '''\
                    def letter_grade(score):
                        if score >= 90:
                            return "A"
                        if score >= 80:
                            return "C"
                        if score >= 70:
                            return "B"
                        if score >= 60:
                            return "D"
                        return "F"
                    '''
                ),
            },
        ],
    },
    {
        "slug": "triangle_classifier",
        "title": "Triangle classifier",
        "entrypoint": "classify_triangle",
        "signature": "classify_triangle(a: float, b: float, c: float) -> str",
        "params": [
            {"name": "a", "type": "float", "note": "side length"},
            {"name": "b", "type": "float", "note": "side length"},
            {"name": "c", "type": "float", "note": "side length"},
        ],
        "requirement": dedent(
            """\
            As a geometry tool, I want classify_triangle(a, b, c) to classify three
            side lengths:
              - "invalid"      if any side <= 0, or the two shortest sides do not
                               sum to strictly more than the longest (degenerate
                               triangles such as 1, 2, 3 are invalid)
              - "equilateral"  if all three sides are equal
              - "isosceles"    if exactly two sides are equal
              - "scalene"      if all three sides differ

            Validity is checked first. Note isosceles must catch any of the three
            equal pairs, e.g. a == c even when b differs."""
        ),
        "canonical_inputs": [[3, 3, 3], [3, 3, 5], [5, 3, 5], [3, 4, 5], [1, 2, 3]],
        "reference": dedent(
            '''\
            def classify_triangle(a, b, c):
                sides = sorted([a, b, c])
                if sides[0] <= 0 or sides[0] + sides[1] <= sides[2]:
                    return "invalid"
                if a == b == c:
                    return "equilateral"
                if a == b or b == c or a == c:
                    return "isosceles"
                return "scalene"
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "Degenerate check uses '<' not '<=', so 1,2,3 is wrongly valid.",
                "code": dedent(
                    '''\
                    def classify_triangle(a, b, c):
                        sides = sorted([a, b, c])
                        if sides[0] <= 0 or sides[0] + sides[1] < sides[2]:
                            return "invalid"
                        if a == b == c:
                            return "equilateral"
                        if a == b or b == c or a == c:
                            return "isosceles"
                        return "scalene"
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "Equilateral case dropped, so 3,3,3 is reported isosceles.",
                "code": dedent(
                    '''\
                    def classify_triangle(a, b, c):
                        sides = sorted([a, b, c])
                        if sides[0] <= 0 or sides[0] + sides[1] <= sides[2]:
                            return "invalid"
                        if a == b or b == c or a == c:
                            return "isosceles"
                        return "scalene"
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Isosceles misses the a == c pair.",
                "code": dedent(
                    '''\
                    def classify_triangle(a, b, c):
                        sides = sorted([a, b, c])
                        if sides[0] <= 0 or sides[0] + sides[1] <= sides[2]:
                            return "invalid"
                        if a == b == c:
                            return "equilateral"
                        if a == b or b == c:
                            return "isosceles"
                        return "scalene"
                    '''
                ),
            },
        ],
    },
    {
        "slug": "roman_numeral",
        "title": "Integer to Roman numeral",
        "entrypoint": "int_to_roman",
        "signature": "int_to_roman(n: int) -> str",
        "params": [{"name": "n", "type": "int", "note": "an integer 1-3999"}],
        "requirement": dedent(
            """\
            As a typography tool, I want int_to_roman(n) to convert an integer from 1
            to 3999 into its Roman-numeral string.

            It must use the subtractive forms: 4 is "IV" (not "IIII"), 9 is "IX", 40
            is "XL", 90 is "XC", 400 is "CD", 900 is "CM". Examples: 4 -> "IV",
            58 -> "LVIII", 1994 -> "MCMXCIV"."""
        ),
        "canonical_inputs": [[4], [9], [58], [1994], [40]],
        "reference": dedent(
            '''\
            def int_to_roman(n):
                vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
                syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
                out = []
                for v, s in zip(vals, syms):
                    while n >= v:
                        out.append(s)
                        n -= v
                return "".join(out)
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "Subtractive 'IV' replaced by additive 'IIII', so 4 -> 'IIII'.",
                "code": dedent(
                    '''\
                    def int_to_roman(n):
                        vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
                        syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IIII", "I"]
                        out = []
                        for v, s in zip(vals, syms):
                            while n >= v:
                                out.append(s)
                                n -= v
                        return "".join(out)
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "Loop uses '>' not '>=', dropping the last unit (58 -> 'LVII').",
                "code": dedent(
                    '''\
                    def int_to_roman(n):
                        vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
                        syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
                        out = []
                        for v, s in zip(vals, syms):
                            while n > v:
                                out.append(s)
                                n -= v
                        return "".join(out)
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Thousands symbol wrong ('D' for 1000), so 1994 -> 'DCMXCIV'.",
                "code": dedent(
                    '''\
                    def int_to_roman(n):
                        vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
                        syms = ["D", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
                        out = []
                        for v, s in zip(vals, syms):
                            while n >= v:
                                out.append(s)
                                n -= v
                        return "".join(out)
                    '''
                ),
            },
        ],
    },
    {
        "slug": "days_in_month",
        "title": "Days in month",
        "entrypoint": "days_in_month",
        "signature": "days_in_month(month: int, year: int) -> int",
        "params": [
            {"name": "month", "type": "int", "note": "month number 1-12"},
            {"name": "year", "type": "int", "note": "a Gregorian year"},
        ],
        "requirement": dedent(
            """\
            As a date library, I want days_in_month(month, year) to return the number
            of days in a given month:
              - April, June, September, November (4, 6, 9, 11) -> 30
              - February -> 29 in a leap year, otherwise 28
              - every other month -> 31

            February depends on the full Gregorian leap rule, so February 1900 has 28
            days but February 2000 has 29."""
        ),
        "canonical_inputs": [[2, 2000], [2, 1900], [2, 2024], [11, 2023], [1, 2023]],
        "reference": dedent(
            '''\
            def days_in_month(month, year):
                if month == 2:
                    leap = year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)
                    return 29 if leap else 28
                if month in (4, 6, 9, 11):
                    return 30
                return 31
            '''
        ),
        "mutants": [
            {
                "key": "m1",
                "description": "February always returns 29 (ignores the leap check).",
                "code": dedent(
                    '''\
                    def days_in_month(month, year):
                        if month == 2:
                            return 29
                        if month in (4, 6, 9, 11):
                            return 30
                        return 31
                    '''
                ),
            },
            {
                "key": "m2",
                "description": "30-day set has 12 instead of 11, so November gets 31, December 30.",
                "code": dedent(
                    '''\
                    def days_in_month(month, year):
                        if month == 2:
                            leap = year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)
                            return 29 if leap else 28
                        if month in (4, 6, 9, 12):
                            return 30
                        return 31
                    '''
                ),
            },
            {
                "key": "m3",
                "description": "Leap rule reduced to '% 4 == 0', so February 1900 wrongly gets 29.",
                "code": dedent(
                    '''\
                    def days_in_month(month, year):
                        if month == 2:
                            leap = year % 4 == 0
                            return 29 if leap else 28
                        if month in (4, 6, 9, 11):
                            return 30
                        return 31
                    '''
                ),
            },
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
