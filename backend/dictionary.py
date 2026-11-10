"""Dictionary lookup service.

The service owns cache/fallback behaviour. Concrete sources live in
`backend.providers` and can be swapped without changing the API or the UI.

Default order:
  1. ECDICT offline subset (MIT, Chinese definitions, no network)
  2. Wiktionary (online, English definitions, only on local miss)

Override for experiments:
    set LEXIREAD_DICTIONARY_PROVIDERS=ecdict,wiktionary
"""
from __future__ import annotations

import re
from typing import Optional

from .providers import (
    DictionaryProvider,
    ProviderError,
    build_providers,
    describe_providers,
    provider_ids,
)
from .storage import cache_word, get_cached_word

CACHE_VERSION = "v2"


class DictionaryError(RuntimeError):
    pass


def normalize_query(value: str) -> str:
    value = (value or "").strip().strip("\"'“”‘’.,;:!?()[]{}<>")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^A-Za-z0-9'’\- ]", "", value)
    return value.strip()[:80]


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _normalize_entry(entry: dict, query: str, provider: DictionaryProvider) -> dict:
    definitions = []
    for item in _as_list(entry.get("definitions")):
        if not isinstance(item, dict):
            continue
        meaning = str(item.get("meaning") or "").strip()
        if not meaning:
            continue
        definitions.append(
            {
                "pos": str(item.get("pos") or "").strip(),
                "meaning": meaning,
                "source": str(item.get("source") or provider.name),
            }
        )

    examples = []
    for item in _as_list(entry.get("examples")):
        if not isinstance(item, dict):
            continue
        en = str(item.get("en") or "").strip()
        if not en:
            continue
        examples.append(
            {
                "en": en,
                "zh": str(item.get("zh") or "").strip(),
                "source": str(item.get("source") or "").strip(),
                "audio": str(item.get("audio") or "").strip(),
            }
        )

    phrases = []
    for item in _as_list(entry.get("phrases")):
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase") or "").strip()
        if phrase:
            phrases.append({"phrase": phrase, "meaning": str(item.get("meaning") or "").strip()})

    synonyms = []
    for item in _as_list(entry.get("synonyms")):
        if not isinstance(item, dict):
            continue
        words = [str(word).strip() for word in _as_list(item.get("words")) if str(word).strip()]
        if words:
            synonyms.append(
                {
                    "pos": str(item.get("pos") or "").strip(),
                    "words": words[:8],
                    "meaning": str(item.get("meaning") or "").strip(),
                }
            )

    forms = []
    for item in _as_list(entry.get("forms")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if name and value:
            forms.append({"name": name, "value": value})

    phonetic = entry.get("phonetic") or {}
    audio = entry.get("audio") or {}
    return {
        "word": query,
        "query": query,
        "phonetic": {
            "us": str(phonetic.get("us") or "").strip(),
            "uk": str(phonetic.get("uk") or "").strip(),
        },
        "audio": {
            "us": str(audio.get("us") or "").strip(),
            "uk": str(audio.get("uk") or "").strip(),
        },
        "definitions": definitions,
        "english_definitions": _as_list(entry.get("english_definitions")),
        "examples": examples,
        "phrases": phrases,
        "synonyms": synonyms,
        "forms": forms,
        "exam_tags": [str(tag) for tag in _as_list(entry.get("exam_tags")) if str(tag).strip()],
        "definition_lang": str(entry.get("definition_lang") or "").strip(),
        "matched_form": str(entry.get("matched_form") or "").strip(),
        "source": str(entry.get("source") or provider.source),
        "source_url": str(entry.get("source_url") or provider.source_url),
        "license": str(entry.get("license") or provider.license),
        "provider": provider.id,
        "fetched_at": None,
    }


class DictionaryService:
    def __init__(self, providers: Optional[list[DictionaryProvider]] = None):
        self.providers = providers if providers is not None else build_providers()

    def _cache_key(self, query: str) -> str:
        provider_key = ",".join(provider.id for provider in self.providers) or "none"
        return f"{CACHE_VERSION}|{provider_key}|{query.lower()}"

    def lookup(self, raw_query: str, *, force: bool = False) -> dict:
        query = normalize_query(raw_query)
        if not query:
            raise DictionaryError("请输入要查询的英文单词或短语。")
        cache_key = self._cache_key(query)
        if not force:
            cached = get_cached_word(cache_key)
            if cached:
                cached.pop("_cache", None)
                cached["cached"] = True
                cached["word"] = query
                cached["query"] = query
                return cached

        errors: list[str] = []
        for provider in self.providers:
            try:
                result = provider.lookup(query)
            except ProviderError as exc:
                errors.append(str(exc))
                continue
            except Exception as exc:  # provider bugs should not take down lookups
                errors.append(f"{provider.name}：{exc}")
                continue
            if not result:
                continue
            entry = _normalize_entry(result, query, provider)
            if not entry["definitions"] and not entry["english_definitions"]:
                continue
            cache_word(cache_key, entry)
            entry["cached"] = False
            return entry

        # When all else fails, an older copy is better than a dead drawer.
        stale = get_cached_word(cache_key)
        if stale:
            stale.pop("_cache", None)
            stale["cached"] = True
            stale["stale"] = True
            stale["word"] = query
            stale["query"] = query
            return stale

        detail = "；".join(dict.fromkeys(errors))[:500]
        if " " in query:
            message = "这个词组本地词库暂未收录，在线词典也没有结果。可以先点击其中单个单词学习。"
        else:
            message = f"暂时查不到 “{query}” 的释义。"
        if detail:
            message += f"（{detail}）"
        raise DictionaryError(message)


_service = DictionaryService()


def lookup(raw_query: str, *, force: bool = False) -> dict:
    return _service.lookup(raw_query, force=force)


def status() -> dict:
    return {
        "providers": describe_providers(),
        "configured_order": provider_ids(),
        "cache_version": CACHE_VERSION,
    }
