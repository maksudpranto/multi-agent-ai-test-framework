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
