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
