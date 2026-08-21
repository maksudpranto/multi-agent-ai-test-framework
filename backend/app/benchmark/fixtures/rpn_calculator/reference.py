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
