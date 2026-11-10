"""SQLite persistence for settings, wordbook and lookup caches."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from .config import DB_PATH, DEFAULT_SETTINGS

_DB_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wordbook (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE COLLATE NOCASE,
    data TEXT NOT NULL,
    source TEXT DEFAULT '',
    source_title TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'learning',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dictionary_cache (
    word TEXT PRIMARY KEY COLLATE NOCASE,
    data TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _DB_LOCK, connect() as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _deep_merge(base: dict, patch: dict) -> dict:
    result = json.loads(json.dumps(base))
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_settings() -> dict:
    patch: dict[str, Any] = {"ai": {}, "learning": {}}
    mapping = {
        "LEXIREAD_AI_BASE_URL": ("ai", "base_url"),
        "LEXIREAD_AI_API_KEY": ("ai", "api_key"),
        "LEXIREAD_AI_MODEL": ("ai", "model"),
        "LEXIREAD_EXAM": ("learning", "exam"),
    }
    for env_name, (section, key) in mapping.items():
        value = os.environ.get(env_name)
        if value:
            patch[section][key] = value
    return patch


def get_settings() -> dict:
    stored: dict[str, Any] = {}
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    for row in rows:
        try:
            stored[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            continue
    merged = _deep_merge(DEFAULT_SETTINGS, stored)
    return _deep_merge(merged, _env_settings())


def public_settings() -> dict:
    settings = get_settings()
    key = settings["ai"].get("api_key", "")
    settings["ai"]["api_key_set"] = bool(key)
    settings["ai"]["api_key_masked"] = ("••••••••" + key[-4:]) if len(key) >= 8 else ("••••••••" if key else "")
    settings["ai"].pop("api_key", None)
    return settings


def update_settings(patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("设置格式不正确")
    with _DB_LOCK, connect() as conn:
        for section in ("ai", "learning"):
            if not isinstance(patch.get(section), dict):
                continue
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (section,)).fetchone()
            current = {}
            if row:
                try:
                    current = json.loads(row["value"])
                except json.JSONDecodeError:
                    current = {}
            incoming = dict(patch[section])
            if "api_key" in incoming:
                key = str(incoming["api_key"] or "").strip()
                if "••" in key:
                    incoming.pop("api_key")
                else:
                    incoming["api_key"] = key
            current = _deep_merge(current, incoming)
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (section, json.dumps(current, ensure_ascii=False)),
            )
    return public_settings()


def is_ai_configured() -> bool:
    settings = get_settings().get("ai", {})
    return bool(settings.get("api_key") and settings.get("base_url") and settings.get("model"))


# ---------------------------------------------------------------------------
# Wordbook
# ---------------------------------------------------------------------------

def _row_to_word(row: sqlite3.Row) -> dict:
    item = dict(row)
    try:
        item["data"] = json.loads(item["data"])
    except (TypeError, json.JSONDecodeError):
        item["data"] = {}
    return item


def list_words(status: Optional[str] = None, search: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM wordbook"
    clauses = []
    params: list[Any] = []
    if status in ("learning", "mastered"):
        clauses.append("status = ?")
        params.append(status)
    if search:
        clauses.append("(word LIKE ? OR data LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_word(row) for row in rows]


def get_word(word: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM wordbook WHERE word = ? COLLATE NOCASE", (word.strip(),)).fetchone()
    return _row_to_word(row) if row else None


def save_word(
    word: str,
    data: dict,
    source: str = "",
    source_title: str = "",
) -> dict:
    clean = (word or "").strip()
    if not clean:
        raise ValueError("单词不能为空")
    stamp = now_iso()
    payload = json.dumps(data or {"word": clean}, ensure_ascii=False)
    with _DB_LOCK, connect() as conn:
        existing = conn.execute("SELECT id FROM wordbook WHERE word = ? COLLATE NOCASE", (clean,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE wordbook SET data = ?, source = COALESCE(NULLIF(?, ''), source), "
                "source_title = COALESCE(NULLIF(?, ''), source_title), updated_at = ? WHERE id = ?",
                (payload, source, source_title, stamp, existing["id"]),
            )
            row = conn.execute("SELECT * FROM wordbook WHERE id = ?", (existing["id"],)).fetchone()
        else:
            conn.execute(
                "INSERT INTO wordbook(word, data, source, source_title, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, 'learning', ?, ?)",
                (clean, payload, source, source_title, stamp, stamp),
            )
            row = conn.execute("SELECT * FROM wordbook WHERE word = ? COLLATE NOCASE", (clean,)).fetchone()
    return _row_to_word(row)


def update_word(word_id: int, *, status: Optional[str] = None, notes: Optional[str] = None) -> Optional[dict]:
    updates = []
    params: list[Any] = []
    if status is not None:
        if status not in ("learning", "mastered"):
            raise ValueError("状态不正确")
        updates.append("status = ?")
        params.append(status)
    if notes is not None:
        updates.append("notes = ?")
        params.append(str(notes)[:2000])
    if not updates:
        raise ValueError("没有需要更新的内容")
    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(word_id)
    with _DB_LOCK, connect() as conn:
        conn.execute(f"UPDATE wordbook SET {', '.join(updates)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM wordbook WHERE id = ?", (word_id,)).fetchone()
    return _row_to_word(row) if row else None


def delete_word(word_id: int) -> bool:
    with _DB_LOCK, connect() as conn:
        cursor = conn.execute("DELETE FROM wordbook WHERE id = ?", (word_id,))
    return cursor.rowcount > 0


def wordbook_stats() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM wordbook GROUP BY status").fetchall()
    counts = {row["status"]: row["n"] for row in rows}
    return {
        "total": sum(counts.values()),
        "learning": counts.get("learning", 0),
        "mastered": counts.get("mastered", 0),
    }


# ---------------------------------------------------------------------------
# Dictionary cache
# ---------------------------------------------------------------------------

def get_cached_word(word: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT data, fetched_at FROM dictionary_cache WHERE word = ? COLLATE NOCASE", (word,)
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except json.JSONDecodeError:
        return None
    data["_cache"] = {"fetched_at": row["fetched_at"], "age": max(0, time.time() - row["fetched_at"])}
    return data


def cache_word(word: str, data: dict) -> None:
    with _DB_LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO dictionary_cache(word, data, fetched_at) VALUES(?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET data = excluded.data, fetched_at = excluded.fetched_at",
            (word.lower(), json.dumps(data, ensure_ascii=False), time.time()),
        )


# ---------------------------------------------------------------------------
# AI cache
# ---------------------------------------------------------------------------

def get_ai_cache(cache_key: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT data, created_at FROM ai_cache WHERE cache_key = ?", (cache_key,)).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except json.JSONDecodeError:
        return None
    data.setdefault("_cache", {"created_at": row["created_at"]})
    return data


def put_ai_cache(cache_key: str, data: dict) -> None:
    with _DB_LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO ai_cache(cache_key, data, created_at) VALUES(?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET data = excluded.data, created_at = excluded.created_at",
            (cache_key, json.dumps(data, ensure_ascii=False), time.time()),
        )


def clear_caches(kind: str = "all") -> None:
    with _DB_LOCK, connect() as conn:
        if kind in ("all", "dictionary"):
            conn.execute("DELETE FROM dictionary_cache")
        if kind in ("all", "ai"):
            conn.execute("DELETE FROM ai_cache")


def clear_wordbook() -> None:
    with _DB_LOCK, connect() as conn:
        conn.execute("DELETE FROM wordbook")


def settings_for_ai() -> dict:
    return get_settings().get("ai", {})
