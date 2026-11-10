"""Online fallback using the Free Dictionary API (Wiktionary data)."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from .base import DictionaryProvider, ProviderError

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
HEADERS = {
    "User-Agent": "LexiRead/1.0 (open-source English reading app)",
    "Accept": "application/json",
}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


class WiktionaryProvider(DictionaryProvider):
    id = "wiktionary"
    name = "Wiktionary 在线补充"
    source = "Wiktionary / Free Dictionary API"
    source_url = "https://en.wiktionary.org/"
    license = "CC BY-SA"
    definition_lang = "en"

    def lookup(self, query: str) -> dict | None:
        if not query or len(query) > 80:
            return None
        try:
            response = requests.get(
                f"{API_URL}/{quote(query)}",
                headers=HEADERS,
                timeout=9,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"在线词典连接失败：{exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ProviderError(f"在线词典返回 HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("在线词典返回格式异常") from exc
        entries = _as_list(payload)
        if not entries or not isinstance(entries[0], dict):
            return None

        definitions = []
        examples = []
        synonyms: list[str] = []
        phonetic = ""
        audio = ""
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            phonetic = phonetic or _text(entry.get("phonetic"))
            for item in _as_list(entry.get("phonetics")):
                if not isinstance(item, dict):
                    continue
                phonetic = phonetic or _text(item.get("text"))
                if not audio and item.get("audio"):
                    audio = str(item["audio"])
                    if audio.startswith("//"):
                        audio = "https:" + audio
            for meaning in _as_list(entry.get("meanings")):
                if not isinstance(meaning, dict):
                    continue
                pos = _text(meaning.get("partOfSpeech"))
                for definition in _as_list(meaning.get("definitions")):
                    if not isinstance(definition, dict):
                        continue
                    value = _text(definition.get("definition"))
                    if value:
                        definitions.append(
                            {
                                "pos": f"{pos}." if pos and not pos.endswith(".") else pos,
                                "meaning": value,
                                "source": "Wiktionary",
                            }
                        )
                    if definition.get("example") and len(examples) < 4:
                        examples.append(
                            {
                                "en": _text(definition["example"]),
                                "zh": "",
                                "source": "Wiktionary",
                                "audio": "",
                            }
                        )
                    for synonym in _as_list(definition.get("synonyms"))[:5]:
                        synonym = _text(synonym)
                        if synonym:
                            synonyms.append(synonym)
                for synonym in _as_list(meaning.get("synonyms"))[:5]:
                    synonym = _text(synonym)
                    if synonym:
                        synonyms.append(synonym)
        if not definitions:
            return None
        return {
            "word": query,
            "phonetic": {"us": phonetic, "uk": phonetic},
            "audio": {"us": audio, "uk": audio},
            "definitions": definitions[:8],
            "english_definitions": [],
            "examples": examples,
            "phrases": [],
            "synonyms": [{"pos": "", "words": list(dict.fromkeys(synonyms))[:8], "meaning": ""}]
            if synonyms
            else [],
            "forms": [],
            "exam_tags": [],
            "definition_lang": "en",
            "source": self.source,
            "source_url": self.source_url,
            "license": self.license,
        }
