import re

WORD_RE = re.compile(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)?\b")


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))
