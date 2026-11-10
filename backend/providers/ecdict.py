"""Offline English-Chinese dictionary backed by an ECDICT subset.

The bundled data is generated from ECDICT (MIT License):
https://github.com/skywind3000/ECDICT
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache

from ..config import BUNDLED_DATA_DIR
from .base import DictionaryProvider, parse_pos

DATA_PATH = BUNDLED_DATA_DIR / "ecdict_subset.json.gz"

EXCHANGE_LABELS = {
    "p": "过去式",
    "d": "过去分词",
    "i": "现在分词",
    "3": "第三人称单数",
    "s": "复数",
    "r": "比较级",
    "t": "最高级",
    "0": "原形",
}


def _parse_exchange(value: str) -> dict[str, list[str]]:
    forms: dict[str, list[str]] = {}
    for chunk in (value or "").split("/"):
        if ":" not in chunk:
            continue
        label, raw = chunk.split(":", 1)
        label = label.strip()
        if label not in EXCHANGE_LABELS:
            continue
        values = [item.strip() for item in re.split(r"[,/]", raw) if item.strip()]
        if values:
            forms.setdefault(label, []).extend(values)
    return forms


@lru_cache(maxsize=1)
def _load_data() -> tuple[dict[str, dict], dict[str, str]]:
    if not DATA_PATH.exists():
        return {}, {}
    with gzip.open(DATA_PATH, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    aliases: dict[str, str] = {}
    for key, entry in data.items():
        exchange = entry.get("exchange", "")
        for values in _parse_exchange(exchange).values():
            for value in values:
                form = value.lower().strip()
                if form and form != key and form not in data and form not in aliases:
                    aliases[form] = key
    return data, aliases


def _morphology_variants(word: str) -> list[str]:
    variants: list[str] = []
    if word.endswith("'s"):
        variants.append(word[:-2])
    if word.endswith("s'"):
        variants.append(word[:-1])
    if word.endswith("ies") and len(word) > 4:
        variants.append(word[:-3] + "y")
    if word.endswith("es") and len(word) > 3:
        variants.append(word[:-2])
    if word.endswith("s") and len(word) > 2:
        variants.append(word[:-1])
    if word.endswith("ied") and len(word) > 4:
        variants.append(word[:-3] + "y")
    if word.endswith("ed") and len(word) > 3:
        variants.append(word[:-2])
        if len(word) > 4 and word[-3] == word[-4]:
            variants.append(word[:-3])
    if word.endswith("ing") and len(word) > 4:
        variants.append(word[:-3])
        variants.append(word[:-3] + "e")
        if len(word) > 5 and word[-4] == word[-5]:
            variants.append(word[:-4])
    if word.endswith("er") and len(word) > 3:
        variants.append(word[:-2])
    if word.endswith("est") and len(word) > 4:
        variants.append(word[:-3])
    return [item for item in dict.fromkeys(variants) if item]


def _find_entry(query: str) -> tuple[str, dict] | tuple[None, None]:
    data, aliases = _load_data()
    word = query.lower().strip()
    candidates = [word, *_morphology_variants(word)]
    for candidate in candidates:
        if candidate in data:
            return candidate, data[candidate]
        if candidate in aliases:
            canonical = aliases[candidate]
            if canonical in data:
                return canonical, data[canonical]
    return None, None


def _clean_phonetic(value: str) -> str:
    return (value or "").replace("ә", "ə").strip("[]/")


def available() -> bool:
    return DATA_PATH.exists()


def entry_count() -> int:
    return len(_load_data()[0])


class EcdictProvider(DictionaryProvider):
    id = "ecdict"
    name = "ECDICT 离线词库"
    source = "ECDICT 本地词库"
    source_url = "https://github.com/skywind3000/ECDICT"
    license = "MIT"
    definition_lang = "zh"

    def lookup(self, query: str) -> dict | None:
        canonical, entry = _find_entry(query)
        if not entry:
            return None

        definitions = []
        for line in entry.get("translations", []):
            pos, meaning = parse_pos(line)
            if meaning:
                definitions.append({"pos": pos, "meaning": meaning, "source": "ECDICT"})
            if len(definitions) >= 6:
                break
        if not definitions:
            return None

        forms = []
        exchange = _parse_exchange(entry.get("exchange", ""))
        for label, values in exchange.items():
            forms.append(
                {
                    "name": EXCHANGE_LABELS[label],
                    "value": " / ".join(dict.fromkeys(values)),
                }
            )

        phonetic = _clean_phonetic(entry.get("phonetic", ""))
        matched = canonical if canonical and canonical != query.lower() else ""
        return {
            "word": query,
            "phonetic": {"us": phonetic, "uk": phonetic},
            "audio": {"us": "", "uk": ""},
            "definitions": definitions,
            "english_definitions": [],
            "examples": [],
            "phrases": [],
            "synonyms": [],
            "forms": forms,
            "exam_tags": entry.get("tags", []),
            "definition_lang": "zh",
            "source": self.source,
            "source_url": self.source_url,
            "license": self.license,
            "matched_form": matched,
        }
