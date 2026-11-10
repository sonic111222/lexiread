"""HTTP API for the LexiRead single-page app."""
from __future__ import annotations

import csv
import io
import time
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, send_from_directory

from . import ai, analyzer, dictionary, ocr
from .config import APP_NAME, APP_TITLE, PROVIDER_PRESETS, UPLOAD_DIR
from .samples import get_sample, sample_list
from .storage import (
    clear_caches,
    clear_wordbook,
    delete_word,
    list_words,
    public_settings,
    save_word,
    update_settings,
    update_word,
    wordbook_stats,
)

api = Blueprint("api", __name__)
_OCR_CACHE: dict = {"checked_at": 0, "data": None}


def _ok(data=None, **extra):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def _error(message: str, status: int = 400, code: str = "error", **extra):
    payload = {"ok": False, "error": message, "code": code}
    payload.update(extra)
    return jsonify(payload), status


@api.get("/health")
def health():
    return _ok(
        {
            "name": APP_NAME,
            "title": APP_TITLE,
            "ai": ai.status(),
            "ocr": _ocr_status(),
        }
    )


def _ocr_status() -> dict:
    now = time.time()
    if _OCR_CACHE["data"] and now - _OCR_CACHE["checked_at"] < 120:
        return _OCR_CACHE["data"]
    data = ocr.engine_status()
    _OCR_CACHE.update({"checked_at": now, "data": data})
    return data


@api.get("/bootstrap")
def bootstrap():
    return _ok(
        {
            "app": {"name": APP_NAME, "title": APP_TITLE, "version": "1.0.0"},
            "settings": public_settings(),
            "ai_status": ai.status(),
            "ocr": _ocr_status(),
            "wordbook": wordbook_stats(),
            "samples": sample_list(),
            "provider_presets": PROVIDER_PRESETS,
            "dictionary": dictionary.status(),
        }
    )


@api.post("/ocr")
def run_ocr():
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return _error("请选择一张题目图片。", 400, "no_file")
    try:
        normalized, preview_url, original_name = ocr.save_upload(upload)
    except ocr.OcrError as exc:
        return _error(str(exc), 400, "image_error")
    try:
        result = ocr.recognize(normalized)
    except ocr.OcrError as exc:
        return _error(str(exc), 422, "ocr_failed", preview_url=preview_url)
    return _ok(
        {
            "text": result["text"],
            "meta": result["meta"],
            "preview_url": preview_url,
            "original_name": original_name,
        }
    )


@api.get("/uploads/<path:name>")
def uploaded_image(name: str):
    safe_name = Path(name).name
    return send_from_directory(UPLOAD_DIR, safe_name, max_age=3600)


@api.post("/analyze")
def analyze_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    title = (data.get("title") or "").strip()
    if not text.strip():
        return _error("没有可分析的文本。", 400, "empty_text")
    if len(text) > 120000:
        return _error("文本过长，请分篇处理（不超过 12 万字符）。", 413, "too_long")
    try:
        result = analyzer.analyze(text, override_title=title)
    except ValueError as exc:
        return _error(str(exc), 400, "analyze_error")
    return _ok(result)


@api.post("/ai/analyze")
def ai_analyze():
    if not ai.is_configured():
        return _error("还没有连接 AI。请先在设置页填写 API 信息。", 400, "ai_not_configured")
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    title = (data.get("title") or "").strip()
    if not text.strip():
        return _error("缺少文章文本。", 400, "empty_text")
    try:
        analysis = analyzer.analyze(text, override_title=title)
        result = ai.analyze(analysis, force=bool(data.get("force")))
    except ValueError as exc:
        return _error(str(exc), 400, "analyze_error")
    except ai.AIError as exc:
        return _error(str(exc), 502, "ai_error")
    return _ok(result, analysis=analysis)


@api.get("/samples")
def samples():
    return _ok(sample_list())


@api.get("/samples/<sample_id>")
def sample_detail(sample_id: str):
    sample = get_sample(sample_id)
    if not sample:
        return _error("示例不存在。", 404, "not_found")
    return _ok(sample)


@api.get("/word/<path:word>")
def word_lookup(word: str):
    force = request.args.get("force") in ("1", "true", "yes")
    try:
        entry = dictionary.lookup(word, force=force)
    except dictionary.DictionaryError as exc:
        return _error(str(exc), 404, "word_not_found")
    return _ok(entry)


@api.get("/wordbook")
def get_wordbook():
    status = request.args.get("status")
    search = request.args.get("search")
    items = list_words(status=status or None, search=search or None)
    return _ok({"items": items, "stats": wordbook_stats()})


@api.post("/wordbook")
def add_to_wordbook():
    data = request.get_json(silent=True) or {}
    word = (data.get("word") or "").strip()
    if not word:
        return _error("单词不能为空。", 400, "empty_word")
    entry = data.get("entry")
    if not isinstance(entry, dict) or not entry.get("definitions"):
        try:
            entry = dictionary.lookup(word)
        except dictionary.DictionaryError as exc:
            return _error(str(exc), 404, "word_not_found")
    try:
        item = save_word(
            word,
            entry,
            source=(data.get("source") or "")[:1000],
            source_title=(data.get("source_title") or "")[:200],
        )
    except ValueError as exc:
        return _error(str(exc), 400, "save_error")
    return jsonify({"ok": True, "data": {"item": item, "stats": wordbook_stats()}})


@api.patch("/wordbook/<int:word_id>")
def patch_word(word_id: int):
    data = request.get_json(silent=True) or {}
    try:
        item = update_word(word_id, status=data.get("status"), notes=data.get("notes"))
    except ValueError as exc:
        return _error(str(exc), 400, "update_error")
    if not item:
        return _error("这个词不在生词本中。", 404, "not_found")
    return jsonify({"ok": True, "data": {"item": item, "stats": wordbook_stats()}})


@api.delete("/wordbook/<int:word_id>")
def remove_word(word_id: int):
    deleted = delete_word(word_id)
    if not deleted:
        return _error("这个词不在生词本中。", 404, "not_found")
    return jsonify({"ok": True, "data": {"stats": wordbook_stats()}})


@api.post("/wordbook/clear")
def clear_all_words():
    clear_wordbook()
    return jsonify({"ok": True, "data": {"stats": wordbook_stats()}})


@api.get("/wordbook/export")
def export_wordbook():
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
    content = "\ufeff" + stream.getvalue()
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=lexiread-wordbook.csv"},
    )


@api.get("/settings")
def get_settings():
    return _ok(
        {
            "settings": public_settings(),
            "presets": PROVIDER_PRESETS,
            "ai_status": ai.status(),
        }
    )


@api.put("/settings")
def put_settings():
    data = request.get_json(silent=True) or {}
    try:
        updated = update_settings(data)
    except ValueError as exc:
        return _error(str(exc), 400, "settings_error")
    return jsonify({"ok": True, "data": {"settings": updated, "ai_status": ai.status()}})


@api.post("/settings/test")
def test_ai():
    try:
        result = ai.test_connection()
    except ai.AIError as exc:
        return _error(str(exc), 502, "ai_test_failed")
    return _ok(result)


@api.post("/settings/clear-cache")
def clear_cache():
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "all")
    if kind not in ("all", "dictionary", "ai"):
        return _error("未知的缓存类型。", 400)
    clear_caches(kind)
    return _ok({"cleared": kind})
