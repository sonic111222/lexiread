"""Browser-facing service layer used by the Pyodide PWA bridge.

This module mirrors the JSON contract in ``backend/api.py`` without importing
Flask, subprocess-based OCR, or any Windows-only code. The worker serializes
the returned dictionaries to JSON.
"""
from __future__ import annotations

import csv
import io
import time

from backend import ai, analyzer, dictionary, samples
from backend.config import APP_NAME, APP_TITLE, PROVIDER_PRESETS
from backend.ocr_text import correct_text
from backend.storage import (
    clear_caches,
    clear_wordbook,
    delete_word,
    init_db,
    list_words,
    public_settings,
    save_word,
    update_settings,
    update_word,
    wordbook_stats,
)

APP_VERSION = "1.0.0"
OCR_STATUS = {
    "available": True,
    "engine": "Tesseract.js",
    "languages": ["eng"],
    "english_available": True,
    "can_open_language_settings": False,
    "ai_vision_available": False,
    "message": "使用浏览器内置 Tesseract 英文 OCR，图片不会上传。",
}


class BridgeError(RuntimeError):
    def __init__(self, message: str, code: str = "error", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def init() -> dict:
    init_db()
    return {"ok": True}


def health() -> dict:
    return {
        "name": APP_NAME,
        "title": APP_TITLE,
        "version": APP_VERSION,
        "ai": ai.status(),
        "ocr": OCR_STATUS,
    }


def bootstrap() -> dict:
    return {
        "app": {"name": APP_NAME, "title": APP_TITLE, "version": APP_VERSION},
        "settings": public_settings(),
        "ai_status": ai.status(),
        "ocr": OCR_STATUS,
        "wordbook": wordbook_stats(),
        "samples": samples.sample_list(),
        "provider_presets": PROVIDER_PRESETS,
        "dictionary": dictionary.status(),
    }


def sample_list() -> list:
    return samples.sample_list()


def sample_get(sample_id: str) -> dict:
    sample = samples.get_sample(sample_id)
    if not sample:
        raise BridgeError("示例不存在。", "not_found", 404)
    return sample


def analyze(text: str, title: str = "") -> dict:
    text = text or ""
    title = (title or "").strip()
    if not text.strip():
        raise BridgeError("没有可分析的文本。", "empty_text", 400)
    if len(text) > 120000:
        raise BridgeError("文本过长，请分篇处理（不超过 12 万字符）。", "too_long", 413)
    try:
        return analyzer.analyze(text, override_title=title)
    except ValueError as exc:
        raise BridgeError(str(exc), "analyze_error", 400) from exc


def ai_analyze(text: str, title: str = "", force: bool = False) -> dict:
    if not ai.is_configured():
        raise BridgeError("还没有连接 AI。请先在设置页填写 API 信息。", "ai_not_configured", 400)
    text = text or ""
    title = (title or "").strip()
    if not text.strip():
        raise BridgeError("缺少文章文本。", "empty_text", 400)
    try:
        analysis = analyzer.analyze(text, override_title=title)
        result = ai.analyze(analysis, force=bool(force))
    except ValueError as exc:
        raise BridgeError(str(exc), "analyze_error", 400) from exc
    except ai.AIError as exc:
        raise BridgeError(str(exc), "ai_error", 502) from exc
    return result


def word_lookup(word: str, force: bool = False) -> dict:
    try:
        return dictionary.lookup(word, force=bool(force))
    except dictionary.DictionaryError as exc:
        raise BridgeError(str(exc), "word_not_found", 404) from exc


def wordbook_list(status: str = "", search: str = "") -> dict:
    items = list_words(status=status or None, search=search or None)
    return {"items": items, "stats": wordbook_stats()}


def wordbook_add(word: str, entry: dict | None = None, source: str = "", source_title: str = "") -> dict:
    word = (word or "").strip()
    if not word:
        raise BridgeError("单词不能为空。", "empty_word", 400)
    if not isinstance(entry, dict) or not entry.get("definitions"):
        try:
            entry = dictionary.lookup(word)
        except dictionary.DictionaryError as exc:
            raise BridgeError(str(exc), "word_not_found", 404) from exc
    try:
        item = save_word(
            word,
            entry,
            source=(source or "")[:1000],
            source_title=(source_title or "")[:200],
        )
    except ValueError as exc:
        raise BridgeError(str(exc), "save_error", 400) from exc
    return {"item": item, "stats": wordbook_stats()}


def wordbook_update(word_id: int, status: str | None = None, notes: str | None = None) -> dict:
    try:
        item = update_word(int(word_id), status=status, notes=notes)
    except ValueError as exc:
        raise BridgeError(str(exc), "update_error", 400) from exc
    if not item:
        raise BridgeError("这个词不在生词本中。", "not_found", 404)
    return {"item": item, "stats": wordbook_stats()}


def wordbook_delete(word_id: int) -> dict:
    if not delete_word(int(word_id)):
        raise BridgeError("这个词不在生词本中。", "not_found", 404)
    return {"stats": wordbook_stats()}


def wordbook_clear() -> dict:
    clear_wordbook()
    return {"stats": wordbook_stats()}


def wordbook_export() -> str:
    items = list_words()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["单词/短语", "音标", "中文释义", "状态", "来源文章", "原文语境", "收藏时间"])
    for item in items:
        entry = item.get("data") or {}
        phonetic = (entry.get("phonetic") or {}).get("us") or (entry.get("phonetic") or {}).get("uk") or ""
        definitions = entry.get("definitions") or []
        meaning = "；".join(
            (f"[{d.get('pos')}] " if d.get("pos") else "") + str(d.get("meaning", ""))
            for d in definitions[:4]
        )
        writer.writerow(
            [
                item.get("word", ""),
                phonetic,
                meaning,
                "已掌握" if item.get("status") == "mastered" else "学习中",
                item.get("source_title", ""),
                item.get("source", ""),
                item.get("created_at", ""),
            ]
        )
    return "\ufeff" + stream.getvalue()


def settings_get() -> dict:
    return {
        "settings": public_settings(),
        "presets": PROVIDER_PRESETS,
        "ai_status": ai.status(),
    }


def settings_save(patch: dict) -> dict:
    try:
        updated = update_settings(patch or {})
    except ValueError as exc:
        raise BridgeError(str(exc), "settings_error", 400) from exc
    return {"settings": updated, "ai_status": ai.status()}


def ai_test() -> dict:
    try:
        return ai.test_connection()
    except ai.AIError as exc:
        raise BridgeError(str(exc), "ai_test_failed", 502) from exc


def cache_clear(kind: str = "all") -> dict:
    if kind not in ("all", "dictionary", "ai"):
        raise BridgeError("未知的缓存类型。", "unknown_cache", 400)
    clear_caches(kind)
    return {"cleared": kind}


def ocr_clean(text: str) -> str:
    return correct_text(text or "")


def now() -> float:
    return time.time()
