"""The executable micro-benchmark corpus (authoritative source).

Each entry is a small, pure Python function with:
  - a natural-language `requirement` the pipeline generates tests from,
  - an `entrypoint` + `signature` the fault-detection harness calls,
  - a correct `reference` implementation that acts as the test ORACLE,
  - `canonical_inputs`: deterministic fallback argument lists (comprehensive
    enough to kill every mutant), and
  - four `mutants`: the reference with one deliberate, edge-targeted bug.

Design for a fair, discriminating benchmark (this is what makes the thesis
comparison meaningful rather than a ceiling):

  * The requirements are written like REAL requirements — they state the core
    behaviour but do not enumerate every corner case. The edge cases (empty
    input, boundary values, malformed input, ordering, wrap-around, …) must be
    *discovered* by a thorough tester, not read off the spec. That is exactly
    the work the multi-agent analysis + Reviewer⇄Consensus debate is meant to do.
  * Each mutant hides in one such edge, so it is killed ONLY by an input that
    exercises that edge. A thin suite (a happy path plus one obvious error)
    kills the obvious mutants and misses the edge ones; a suite that covers the
    corners kills more. That spread is the signal the experiment measures.

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
        "slug": "ipv4_validator",
        "title": "IPv4 address validator",
        "entrypoint": "is_valid_ipv4",
        "signature": "is_valid_ipv4(s: str) -> bool",
        "params": [{"name": "s", "type": "str", "note": "the string to validate"}],
        "requirement": dedent(
            """\
            As a form-validation feature, I want is_valid_ipv4(s) to return True when a
            string is a well-formed IPv4 address and False otherwise.

            A well-formed address is four decimal numbers separated by dots, and each
            number is in the range 0 to 255. For example "192.168.0.1" is valid and
            "10.0.0.256" is not. The function returns a boolean; it never raises."""
        ),
        "canonical_inputs": [
            ["1.2.3.4"], ["0.0.0.0"], ["255.255.255.255"], ["256.1.1.1"],
            ["01.2.3.4"], ["1.2.3.4.5"], ["1.2.3"], ["1.300.1.1"], ["a.b.c.d"],
        ],
        "reference": dedent(
            '''\
            def is_valid_ipv4(s):
                parts = s.split(".")
                if len(parts) != 4:
                    return False
                for p in parts:
                    if not p.isdigit():
                        return False
                    if len(p) > 1 and p[0] == "0":
                        return False
                    if int(p) > 255:
                        return False
                return True
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "No upper-bound check, so octets above 255 are accepted.",
             "code": dedent(
                '''\
                def is_valid_ipv4(s):
                    parts = s.split(".")
                    if len(parts) != 4:
                        return False
                    for p in parts:
                        if not p.isdigit():
                            return False
                        if len(p) > 1 and p[0] == "0":
                            return False
                    return True
                ''')},
            {"key": "m2", "description": "Leading-zero octets (e.g. '01') are wrongly accepted.",
             "code": dedent(
                '''\
                def is_valid_ipv4(s):
                    parts = s.split(".")
                    if len(parts) != 4:
                        return False
                    for p in parts:
                        if not p.isdigit():
                            return False
                        if int(p) > 255:
                            return False
                    return True
                ''')},
            {"key": "m3", "description": "Accepts 4 OR MORE parts (uses < instead of !=).",
             "code": dedent(
                '''\
                def is_valid_ipv4(s):
                    parts = s.split(".")
                    if len(parts) < 4:
                        return False
                    for p in parts:
                        if not p.isdigit():
                            return False
                        if len(p) > 1 and p[0] == "0":
                            return False
                        if int(p) > 255:
                            return False
                    return True
                ''')},
            {"key": "m4", "description": "Boundary off-by-one: rejects exactly 255 (uses >= 255).",
             "code": dedent(
                '''\
                def is_valid_ipv4(s):
                    parts = s.split(".")
                    if len(parts) != 4:
                        return False
                    for p in parts:
                        if not p.isdigit():
                            return False
                        if len(p) > 1 and p[0] == "0":
                            return False
                        if int(p) >= 255:
                            return False
                    return True
                ''')},
        ],
    },
    {
        "slug": "balanced_brackets",
        "title": "Balanced-brackets checker",
        "entrypoint": "is_balanced",
        "signature": "is_balanced(s: str) -> bool",
        "params": [{"name": "s", "type": "str", "note": "a string possibly containing brackets"}],
        "requirement": dedent(
            """\
            As a code-editor helper, I want is_balanced(s) to check whether the brackets
            in a string are balanced. The three bracket kinds are (), [] and {}.

            Brackets are balanced when every opening bracket is closed by a matching
            closing bracket in the correct order, e.g. "(a[b]{c})" is balanced. Any
            characters that are not brackets are ignored. Returns a boolean."""
        ),
        "canonical_inputs": [
            ["()"], ["([])"], ["([)]"], ["("], [")"], ["(]"], [""], ["a(b)c"], ["())"],
        ],
        "reference": dedent(
            '''\
            def is_balanced(s):
                pairs = {")": "(", "]": "[", "}": "{"}
                stack = []
                for ch in s:
                    if ch in "([{":
                        stack.append(ch)
                    elif ch in ")]}":
                        if not stack or stack.pop() != pairs[ch]:
                            return False
                return not stack
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Closing bracket type is not checked (pops without matching).",
             "code": dedent(
                '''\
                def is_balanced(s):
                    stack = []
                    for ch in s:
                        if ch in "([{":
                            stack.append(ch)
                        elif ch in ")]}":
                            if not stack:
                                return False
                            stack.pop()
                    return not stack
                ''')},
            {"key": "m2", "description": "Leftover unclosed brackets are ignored (always returns True at end).",
             "code": dedent(
                '''\
                def is_balanced(s):
                    pairs = {")": "(", "]": "[", "}": "{"}
                    stack = []
                    for ch in s:
                        if ch in "([{":
                            stack.append(ch)
                        elif ch in ")]}":
                            if not stack or stack.pop() != pairs[ch]:
                                return False
                    return True
                ''')},
            {"key": "m3", "description": "A closing bracket with nothing open is not treated as an error.",
             "code": dedent(
                '''\
                def is_balanced(s):
                    pairs = {")": "(", "]": "[", "}": "{"}
                    stack = []
                    for ch in s:
                        if ch in "([{":
                            stack.append(ch)
                        elif ch in ")]}":
                            if stack and stack.pop() != pairs[ch]:
                                return False
                    return not stack
                ''')},
            {"key": "m4", "description": "Only round brackets are recognised as openers.",
             "code": dedent(
                '''\
                def is_balanced(s):
                    pairs = {")": "(", "]": "[", "}": "{"}
                    stack = []
                    for ch in s:
                        if ch == "(":
                            stack.append(ch)
                        elif ch in ")]}":
                            if not stack or stack.pop() != pairs[ch]:
                                return False
                    return not stack
                ''')},
        ],
    },
    {
        "slug": "slugify",
        "title": "URL slug generator",
        "entrypoint": "slugify",
        "signature": "slugify(s: str) -> str",
        "params": [{"name": "s", "type": "str", "note": "a title or phrase"}],
        "requirement": dedent(
            """\
            As a blog CMS, I want slugify(s) to turn a title into a URL slug.

            The slug is lowercase, with words separated by single hyphens. Letters and
            digits are kept; spaces, hyphens and underscores become hyphens; other
            punctuation is dropped. For example "Hello, World!" becomes "hello-world".
            The result has no leading or trailing hyphen and no doubled hyphens."""
        ),
        "canonical_inputs": [
            ["Hello, World!"], ["  Spaced  "], ["Multiple   Spaces"],
            ["Trailing-"], ["ALL_CAPS"], [""], ["a"],
        ],
        "reference": dedent(
            '''\
            def slugify(s):
                out = []
                for ch in s.lower():
                    if ch.isalnum():
                        out.append(ch)
                    elif ch in " -_":
                        out.append("-")
                slug = "".join(out)
                while "--" in slug:
                    slug = slug.replace("--", "-")
                return slug.strip("-")
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Does not lowercase the input.",
             "code": dedent(
                '''\
                def slugify(s):
                    out = []
                    for ch in s:
                        if ch.isalnum():
                            out.append(ch)
                        elif ch in " -_":
                            out.append("-")
                    slug = "".join(out)
                    while "--" in slug:
                        slug = slug.replace("--", "-")
                    return slug.strip("-")
                ''')},
            {"key": "m2", "description": "Does not collapse repeated hyphens.",
             "code": dedent(
                '''\
                def slugify(s):
                    out = []
                    for ch in s.lower():
                        if ch.isalnum():
                            out.append(ch)
                        elif ch in " -_":
                            out.append("-")
                    return "".join(out).strip("-")
                ''')},
            {"key": "m3", "description": "Does not strip leading/trailing hyphens.",
             "code": dedent(
                '''\
                def slugify(s):
                    out = []
                    for ch in s.lower():
                        if ch.isalnum():
                            out.append(ch)
                        elif ch in " -_":
                            out.append("-")
                    slug = "".join(out)
                    while "--" in slug:
                        slug = slug.replace("--", "-")
                    return slug
                ''')},
            {"key": "m4", "description": "Underscores are dropped instead of becoming hyphens.",
             "code": dedent(
                '''\
                def slugify(s):
                    out = []
                    for ch in s.lower():
                        if ch.isalnum():
                            out.append(ch)
                        elif ch in " -":
                            out.append("-")
                    slug = "".join(out)
                    while "--" in slug:
                        slug = slug.replace("--", "-")
                    return slug.strip("-")
                ''')},
        ],
    },
    {
        "slug": "version_compare",
        "title": "Semantic-version comparator",
        "entrypoint": "compare_versions",
        "signature": "compare_versions(a: str, b: str) -> int",
        "params": [
            {"name": "a", "type": "str", "note": "a dotted version string, e.g. '1.2.0'"},
            {"name": "b", "type": "str", "note": "a dotted version string"},
        ],
        "requirement": dedent(
            """\
            As a package manager, I want compare_versions(a, b) to compare two dotted
            version strings and return -1 if a < b, 0 if they are equal, and 1 if a > b.

            Each component is compared numerically (so 1.10 is newer than 1.9). Missing
            trailing components count as zero, so "1.2" and "1.2.0" are equal."""
        ),
        "canonical_inputs": [
            ["1.0.0", "1.0.0"], ["1.2.0", "1.10.0"], ["1.2", "1.2.0"],
            ["1.0", "1.0.1"], ["1.0.1", "1.0.2"], ["2.0", "1.9"],
        ],
        "reference": dedent(
            '''\
            def compare_versions(a, b):
                pa = [int(x) for x in a.split(".")]
                pb = [int(x) for x in b.split(".")]
                n = max(len(pa), len(pb))
                pa += [0] * (n - len(pa))
                pb += [0] * (n - len(pb))
                for x, y in zip(pa, pb):
                    if x < y:
                        return -1
                    if x > y:
                        return 1
                return 0
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Compares components as strings, so '2' > '10'.",
             "code": dedent(
                '''\
                def compare_versions(a, b):
                    pa = a.split(".")
                    pb = b.split(".")
                    n = max(len(pa), len(pb))
                    pa += ["0"] * (n - len(pa))
                    pb += ["0"] * (n - len(pb))
                    for x, y in zip(pa, pb):
                        if x < y:
                            return -1
                        if x > y:
                            return 1
                    return 0
                ''')},
            {"key": "m2", "description": "No zero-padding, so '1.0' and '1.0.1' compare equal.",
             "code": dedent(
                '''\
                def compare_versions(a, b):
                    pa = [int(x) for x in a.split(".")]
                    pb = [int(x) for x in b.split(".")]
                    for x, y in zip(pa, pb):
                        if x < y:
                            return -1
                        if x > y:
                            return 1
                    return 0
                ''')},
            {"key": "m3", "description": "Sign inverted (returns 1 when a < b).",
             "code": dedent(
                '''\
                def compare_versions(a, b):
                    pa = [int(x) for x in a.split(".")]
                    pb = [int(x) for x in b.split(".")]
                    n = max(len(pa), len(pb))
                    pa += [0] * (n - len(pa))
                    pb += [0] * (n - len(pb))
                    for x, y in zip(pa, pb):
                        if x < y:
                            return 1
                        if x > y:
                            return -1
                    return 0
                ''')},
            {"key": "m4", "description": "Only the first two components are compared.",
             "code": dedent(
                '''\
                def compare_versions(a, b):
                    pa = [int(x) for x in a.split(".")]
                    pb = [int(x) for x in b.split(".")]
                    n = max(len(pa), len(pb))
                    pa += [0] * (n - len(pa))
                    pb += [0] * (n - len(pb))
                    for x, y in zip(pa[:2], pb[:2]):
                        if x < y:
                            return -1
                        if x > y:
                            return 1
                    return 0
                ''')},
        ],
    },
    {
        "slug": "caesar_cipher",
        "title": "Caesar cipher",
        "entrypoint": "caesar_cipher",
        "signature": "caesar_cipher(text: str, shift: int) -> str",
        "params": [
            {"name": "text", "type": "str", "note": "the text to encrypt"},
            {"name": "shift", "type": "int", "note": "how many letters to shift by"},
        ],
        "requirement": dedent(
            """\
            As a puzzle app, I want caesar_cipher(text, shift) to shift each letter of
            text forward through the alphabet by `shift` positions.

            Letters wrap around the end of the alphabet (z shifts to a), and the case of
            each letter is preserved. Characters that are not letters are left
            unchanged. For example caesar_cipher("Abc", 1) returns "Bcd"."""
        ),
        "canonical_inputs": [
            ["abc", 1], ["xyz", 3], ["ABC", 1], ["Hello, World!", 5],
            ["abc", 0], ["abc", 27],
        ],
        "reference": dedent(
            '''\
            def caesar_cipher(text, shift):
                out = []
                for ch in text:
                    if ch.isupper():
                        out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
                    elif ch.islower():
                        out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
                    else:
                        out.append(ch)
                return "".join(out)
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "No wrap-around (drops the modulo), so 'z' overflows past 'z'.",
             "code": dedent(
                '''\
                def caesar_cipher(text, shift):
                    out = []
                    for ch in text:
                        if ch.isupper():
                            out.append(chr(ord(ch) + shift))
                        elif ch.islower():
                            out.append(chr(ord(ch) + shift))
                        else:
                            out.append(ch)
                    return "".join(out)
                ''')},
            {"key": "m2", "description": "Uppercase letters are left unshifted (case not handled).",
             "code": dedent(
                '''\
                def caesar_cipher(text, shift):
                    out = []
                    for ch in text:
                        if ch.islower():
                            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
                        else:
                            out.append(ch)
                    return "".join(out)
                ''')},
            {"key": "m3", "description": "Non-letters are shifted too, corrupting punctuation/spaces.",
             "code": dedent(
                '''\
                def caesar_cipher(text, shift):
                    out = []
                    for ch in text:
                        if ch.isupper():
                            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
                        elif ch.islower():
                            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
                        else:
                            out.append(chr(ord(ch) + shift))
                    return "".join(out)
                ''')},
            {"key": "m4", "description": "Wrap modulus is 25, not 26 — mishandles large shifts.",
             "code": dedent(
                '''\
                def caesar_cipher(text, shift):
                    out = []
                    for ch in text:
                        if ch.isupper():
                            out.append(chr((ord(ch) - 65 + shift) % 25 + 65))
                        elif ch.islower():
                            out.append(chr((ord(ch) - 97 + shift) % 25 + 97))
                        else:
                            out.append(ch)
                    return "".join(out)
                ''')},
        ],
    },
    {
        "slug": "duration_parser",
        "title": "Duration parser",
        "entrypoint": "parse_duration",
        "signature": "parse_duration(s: str) -> int",
        "params": [{"name": "s", "type": "str", "note": "a duration like '1h30m'"}],
        "requirement": dedent(
            """\
            As a scheduling tool, I want parse_duration(s) to turn a short duration
            string into a total number of seconds.

            The string is made of number+unit pieces, where the unit is h (hours),
            m (minutes) or s (seconds), e.g. "1h30m" is 5400 and "45s" is 45. Pieces may
            be combined in any mix. An empty string is 0."""
        ),
        "canonical_inputs": [
            ["1h"], ["30m"], ["45s"], ["1h30m"], ["2h15m30s"], [""], ["90m"],
        ],
        "reference": dedent(
            '''\
            def parse_duration(s):
                import re
                total = 0
                for num, unit in re.findall(r"(\\d+)([hms])", s):
                    n = int(num)
                    if unit == "h":
                        total += n * 3600
                    elif unit == "m":
                        total += n * 60
                    else:
                        total += n
                return total
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Hours use a 60x multiplier instead of 3600x.",
             "code": dedent(
                '''\
                def parse_duration(s):
                    import re
                    total = 0
                    for num, unit in re.findall(r"(\\d+)([hms])", s):
                        n = int(num)
                        if unit == "h":
                            total += n * 60
                        elif unit == "m":
                            total += n * 60
                        else:
                            total += n
                    return total
                ''')},
            {"key": "m2", "description": "Seconds are ignored.",
             "code": dedent(
                '''\
                def parse_duration(s):
                    import re
                    total = 0
                    for num, unit in re.findall(r"(\\d+)([hms])", s):
                        n = int(num)
                        if unit == "h":
                            total += n * 3600
                        elif unit == "m":
                            total += n * 60
                    return total
                ''')},
            {"key": "m3", "description": "Minutes are counted as seconds (no 60x).",
             "code": dedent(
                '''\
                def parse_duration(s):
                    import re
                    total = 0
                    for num, unit in re.findall(r"(\\d+)([hms])", s):
                        n = int(num)
                        if unit == "h":
                            total += n * 3600
                        elif unit == "m":
                            total += n
                        else:
                            total += n
                    return total
                ''')},
            {"key": "m4", "description": "Only the first piece is parsed; the rest is dropped.",
             "code": dedent(
                '''\
                def parse_duration(s):
                    import re
                    total = 0
                    for num, unit in re.findall(r"(\\d+)([hms])", s)[:1]:
                        n = int(num)
                        if unit == "h":
                            total += n * 3600
                        elif unit == "m":
                            total += n * 60
                        else:
                            total += n
                    return total
                ''')},
        ],
    },
    {
        "slug": "rpn_calculator",
        "title": "RPN calculator",
        "entrypoint": "rpn_eval",
        "signature": "rpn_eval(expr: str) -> float",
        "params": [{"name": "expr", "type": "str", "note": "a space-separated RPN expression"}],
        "requirement": dedent(
            """\
            As a calculator engine, I want rpn_eval(expr) to evaluate a reverse-Polish
            (postfix) expression given as space-separated tokens and return the result
            as a float.

            Tokens are numbers and the operators + - * /. Each operator pops the two
            most recent values and applies itself, so "10 2 -" is 8 (the earlier value
            minus the later one) and "3 4 +" is 7. A lone number evaluates to itself."""
        ),
        "canonical_inputs": [
            ["3 4 +"], ["10 2 -"], ["2 3 *"], ["8 2 /"], ["5"], ["1 2 - 3 *"],
        ],
        "reference": dedent(
            '''\
            def rpn_eval(expr):
                stack = []
                for tok in expr.split():
                    if tok in ("+", "-", "*", "/"):
                        b = stack.pop()
                        a = stack.pop()
                        if tok == "+":
                            stack.append(a + b)
                        elif tok == "-":
                            stack.append(a - b)
                        elif tok == "*":
                            stack.append(a * b)
                        else:
                            stack.append(a / b)
                    else:
                        stack.append(float(tok))
                return stack[-1]
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Subtraction operands reversed (computes b - a).",
             "code": dedent(
                '''\
                def rpn_eval(expr):
                    stack = []
                    for tok in expr.split():
                        if tok in ("+", "-", "*", "/"):
                            b = stack.pop()
                            a = stack.pop()
                            if tok == "+":
                                stack.append(a + b)
                            elif tok == "-":
                                stack.append(b - a)
                            elif tok == "*":
                                stack.append(a * b)
                            else:
                                stack.append(a / b)
                        else:
                            stack.append(float(tok))
                    return stack[-1]
                ''')},
            {"key": "m2", "description": "Division operands reversed (computes b / a).",
             "code": dedent(
                '''\
                def rpn_eval(expr):
                    stack = []
                    for tok in expr.split():
                        if tok in ("+", "-", "*", "/"):
                            b = stack.pop()
                            a = stack.pop()
                            if tok == "+":
                                stack.append(a + b)
                            elif tok == "-":
                                stack.append(a - b)
                            elif tok == "*":
                                stack.append(a * b)
                            else:
                                stack.append(b / a)
                        else:
                            stack.append(float(tok))
                    return stack[-1]
                ''')},
            {"key": "m3", "description": "Multiplication is implemented as addition.",
             "code": dedent(
                '''\
                def rpn_eval(expr):
                    stack = []
                    for tok in expr.split():
                        if tok in ("+", "-", "*", "/"):
                            b = stack.pop()
                            a = stack.pop()
                            if tok == "+":
                                stack.append(a + b)
                            elif tok == "-":
                                stack.append(a - b)
                            elif tok == "*":
                                stack.append(a + b)
                            else:
                                stack.append(a / b)
                        else:
                            stack.append(float(tok))
                    return stack[-1]
                ''')},
            {"key": "m4", "description": "Division truncates to an int, losing the float result type.",
             "code": dedent(
                '''\
                def rpn_eval(expr):
                    stack = []
                    for tok in expr.split():
                        if tok in ("+", "-", "*", "/"):
                            b = stack.pop()
                            a = stack.pop()
                            if tok == "+":
                                stack.append(a + b)
                            elif tok == "-":
                                stack.append(a - b)
                            elif tok == "*":
                                stack.append(a * b)
                            else:
                                stack.append(int(a / b))
                        else:
                            stack.append(float(tok))
                    return stack[-1]
                ''')},
        ],
    },
    {
        "slug": "run_length_encode",
        "title": "Run-length encoder",
        "entrypoint": "rle_encode",
        "signature": "rle_encode(s: str) -> str",
        "params": [{"name": "s", "type": "str", "note": "the string to encode"}],
        "requirement": dedent(
            """\
            As a compression utility, I want rle_encode(s) to run-length encode a string:
            each run of the same character becomes that character followed by the count
            of how many times it repeats.

            For example "aaabbc" encodes to "a3b2c1". A single character becomes that
            character followed by 1. The empty string encodes to the empty string."""
        ),
        "canonical_inputs": [["aaabbc"], ["a"], [""], ["abc"], ["aaaa"], ["aabbbba"]],
        "reference": dedent(
            '''\
            def rle_encode(s):
                if not s:
                    return ""
                out = []
                prev = s[0]
                count = 1
                for ch in s[1:]:
                    if ch == prev:
                        count += 1
                    else:
                        out.append(prev + str(count))
                        prev = ch
                        count = 1
                out.append(prev + str(count))
                return "".join(out)
            '''
        ),
        "mutants": [
            {"key": "m1", "description": "Forgets to emit the final run.",
             "code": dedent(
                '''\
                def rle_encode(s):
                    if not s:
                        return ""
                    out = []
                    prev = s[0]
                    count = 1
                    for ch in s[1:]:
                        if ch == prev:
                            count += 1
                        else:
                            out.append(prev + str(count))
                            prev = ch
                            count = 1
                    return "".join(out)
                ''')},
            {"key": "m2", "description": "Run count starts at 0, so every count is one too low.",
             "code": dedent(
                '''\
                def rle_encode(s):
                    if not s:
                        return ""
                    out = []
                    prev = s[0]
                    count = 0
                    for ch in s[1:]:
                        if ch == prev:
                            count += 1
                        else:
                            out.append(prev + str(count))
                            prev = ch
                            count = 1
                    out.append(prev + str(count))
                    return "".join(out)
                ''')},
            {"key": "m3", "description": "Empty input is not special-cased and crashes.",
             "code": dedent(
                '''\
                def rle_encode(s):
                    out = []
                    prev = s[0]
                    count = 1
                    for ch in s[1:]:
                        if ch == prev:
                            count += 1
                        else:
                            out.append(prev + str(count))
                            prev = ch
                            count = 1
                    out.append(prev + str(count))
                    return "".join(out)
                ''')},
            {"key": "m4", "description": "Count is not reset after a run ends.",
             "code": dedent(
                '''\
                def rle_encode(s):
                    if not s:
                        return ""
                    out = []
                    prev = s[0]
                    count = 1
                    for ch in s[1:]:
                        if ch == prev:
                            count += 1
                        else:
                            out.append(prev + str(count))
                            prev = ch
                    out.append(prev + str(count))
                    return "".join(out)
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
