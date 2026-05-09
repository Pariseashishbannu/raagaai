"""Telugu text processing utilities."""


def split_telugu_syllables(text: str) -> list[str]:
    """Split Telugu text into syllable units (aksharas)."""
    syllables = []
    text = text.replace(" ", "")
    i = 0
    while i < len(text):
        char = text[i]
        syllable = char
        i += 1
        while i < len(text) and is_combining_mark(text[i]):
            syllable += text[i]
            i += 1
        syllables.append(syllable)
    return syllables


def is_combining_mark(c: str) -> bool:
    """Check if character is a Telugu combining mark (vowel sign, virama, etc.)."""
    cp = ord(c)
    return (0x0C3E <= cp <= 0x0C56) or (cp == 0x0C4D) or (0x0C01 <= cp <= 0x0C03)


def transliterate_to_latin(telugu_text: str) -> str:
    """Basic Telugu-to-Latin transliteration for display."""
    mapping = {
        "అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ee",
        "ఉ": "u", "ఊ": "oo", "ఎ": "e", "ఏ": "ae",
        "ఒ": "o", "ఓ": "oo", "క": "ka", "ఖ": "kha",
        "గ": "ga", "ఘ": "gha", "చ": "cha", "ఛ": "chha",
        "జ": "ja", "ఝ": "jha", "ట": "ta", "ఠ": "tha",
        "డ": "da", "ఢ": "dha", "ణ": "na", "త": "tha",
        "థ": "thha", "ద": "dha", "ధ": "dhha", "న": "na",
        "ప": "pa", "ఫ": "pha", "బ": "ba", "భ": "bha",
        "మ": "ma", "య": "ya", "ర": "ra", "ల": "la",
        "వ": "va", "శ": "sha", "ష": "sha", "స": "sa",
        "హ": "ha",
    }
    result = []
    for c in telugu_text:
        result.append(mapping.get(c, c))
    return "".join(result)
