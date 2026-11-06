"""Shared untrusted text normalization."""

import unicodedata


def normalize_text(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFC", value.strip())
        if unicodedata.category(char) not in {"Cc", "Cf"}
    )


def search_fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_text(value).casefold().replace("đ", "d"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))
