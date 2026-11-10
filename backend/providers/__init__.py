"""Replaceable dictionary providers.

The app only depends on the `DictionaryProvider` contract. Add a new source by
implementing `lookup()` and registering it in `build_providers()`. Optional
providers can be enabled with:

    LEXIREAD_DICTIONARY_PROVIDERS=ecdict,wiktionary
"""
from __future__ import annotations

import os

from .base import DictionaryProvider, ProviderError
from .ecdict import EcdictProvider, available as ecdict_available, entry_count as ecdict_count
from .wiktionary import WiktionaryProvider

DEFAULT_PROVIDER_ORDER = ("ecdict", "wiktionary")
_REGISTRY: dict[str, type[DictionaryProvider]] = {
    "ecdict": EcdictProvider,
    "wiktionary": WiktionaryProvider,
}


def provider_ids() -> list[str]:
    configured = os.environ.get("LEXIREAD_DICTIONARY_PROVIDERS", "")
    if configured.strip():
        return [item.strip() for item in configured.split(",") if item.strip() in _REGISTRY]
    return list(DEFAULT_PROVIDER_ORDER)


def build_providers() -> list[DictionaryProvider]:
    return [_REGISTRY[item]() for item in provider_ids() if item in _REGISTRY]


def describe_providers() -> list[dict]:
    result = []
    for provider in build_providers():
        info = {
            "id": provider.id,
            "name": provider.name,
            "source": provider.source,
            "source_url": provider.source_url,
            "license": provider.license,
        }
        if provider.id == "ecdict":
            info["available"] = ecdict_available()
            info["entries"] = ecdict_count() if ecdict_available() else 0
        else:
            info["available"] = True
        result.append(info)
    return result


__all__ = [
    "DictionaryProvider",
    "ProviderError",
    "build_providers",
    "describe_providers",
    "provider_ids",
]
