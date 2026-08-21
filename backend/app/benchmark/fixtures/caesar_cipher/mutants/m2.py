def caesar_cipher(text, shift):
    out = []
    for ch in text:
        if ch.islower():
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)
