# Requirement title

<!--
HOW THIS FILE IS USED
The whole content of this file becomes the requirement text. Write in plain
language — the AI reads this text to design test cases, so the clearer and more
specific you are (especially about rules and edge cases), the better the tests.
Delete these comment lines before uploading if you like; they are ignored either
way. Save as .txt or .md and upload it.
-->

## Summary
As a <role>, I want <goal> so that <benefit>.

## Acceptance criteria
- Given <starting state>, when <action>, then <expected result>.
- Given <starting state>, when <action>, then <expected result>.

## Rules and edge cases
- <Boundary or limit, e.g. "amount must be greater than 0 and no more than the balance">
- <What happens on invalid input, e.g. "reject a frozen account with an error">
- <Any exact numbers, ranges, or off-by-one boundaries the tests must check>

## Example
- Input: <example input>
- Expected output: <example result>

---
Example (fill in the blanks like this):

## Summary
As an online banking user, I want to transfer money out of my account so that I
can pay someone.

## Acceptance criteria
- Given a positive amount no greater than my balance, when I transfer, then my
  new balance is the old balance minus the amount.
- Given an amount greater than my balance, when I transfer, then it is rejected.

## Rules and edge cases
- A frozen account cannot transfer at all.
- The amount must be greater than 0.
- Transferring the exact full balance is allowed and leaves a balance of 0.
