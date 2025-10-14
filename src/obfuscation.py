import re


def decode_obfuscated(text: str) -> str:
    if not text:
        return text
    t = text
    replacements = [
        (r"\s*\[?\s*(?:at|AT|＠|\(at\))\s*\]?\s*", "@"),
        (r"\s*\[?\s*(?:dot|DOT|。|\(dot\))\s*\]?\s*", "."),
        (r"\s*\(at\)\s*", "@"),
        (r"\s*\(dot\)\s*", "."),
    ]
    for pat, repl in replacements:
        t = re.sub(pat, repl, t)
    # remove spaces inside email-like strings
    t = re.sub(r"([\w.%+-])\s+(@)\s+([\w.-])", r"\1\2\3", t)
    t = re.sub(r"(@)\s+([\w.-]+)\s*(\.)\s*([A-Za-z]{2,})", r"\1\2\3\4", t)
    return t


def extract_emails_with_obfuscation(text: str) -> list[str]:
    t = decode_obfuscated(text)
    pattern = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
    return pattern.findall(t)





