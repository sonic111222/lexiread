"""Dictionary provider contract and shared helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ProviderError(RuntimeError):
    """A provider could not answer (network, parsing or availability)."""


class DictionaryProvider(ABC):
    """A lookup source that can be swapped without touching the API layer."""

    id = "base"
    name = "Dictionary"
    source = "Dictionary"
    source_url = ""
    license = ""
    definition_lang = ""

    @abstractmethod
    def lookup(self, query: str) -> Optional[dict]:
        """Return a normalized-ish entry dict, or None when not found."""


def parse_pos(meaning: str) -> tuple[str, str]:
    """Split a leading ECDICT/part-of-speech marker from a definition."""
    import re

    value = (meaning or "").strip()
    value = re.sub(r"^\[[^\]]{1,12}\]\s*", "", value)
    match = re.match(
        r"^(n|v|vt|vi|adj|adv|a|ad|prep|conj|pron|art|num|int|aux|abbr|suf|pref|phr)\.\s*(.+)$",
        value,
        re.I,
    )
    if not match:
        return "", value
    pos_map = {
        "a": "adj.",
        "ad": "adv.",
        "n": "n.",
        "v": "v.",
        "vt": "vt.",
        "vi": "vi.",
        "adj": "adj.",
        "adv": "adv.",
        "prep": "prep.",
        "conj": "conj.",
        "pron": "pron.",
        "art": "art.",
        "num": "num.",
        "int": "int.",
        "aux": "aux.",
        "abbr": "abbr.",
        "suf": "suf.",
        "pref": "pref.",
        "phr": "phr.",
    }
    return pos_map.get(match.group(1).lower(), f"{match.group(1).lower()}."), match.group(2).strip()
