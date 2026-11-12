"""Application paths and defaults."""
from __future__ import annotations

import os
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent.parent
FROZEN = bool(getattr(sys, "frozen", False))
# PyInstaller extracts bundled read-only assets into _MEIPASS. Persistent user
# data stays next to the executable so the app works as a portable folder.
RESOURCE_DIR = Path(
    os.environ.get("LEXIREAD_RESOURCE_DIR")
    or (getattr(sys, "_MEIPASS", SOURCE_DIR) if FROZEN else SOURCE_DIR)
)
BASE_DIR = Path(os.environ.get("LEXIREAD_BASE_DIR") or (Path(sys.executable).resolve().parent if FROZEN else SOURCE_DIR))

STATIC_DIR = Path(os.environ.get("LEXIREAD_STATIC_DIR") or (RESOURCE_DIR / "static"))
TOOLS_DIR = RESOURCE_DIR / "tools"
BUNDLED_DATA_DIR = Path(os.environ.get("LEXIREAD_BUNDLED_DATA_DIR") or (RESOURCE_DIR / "backend" / "data"))
DATA_DIR = Path(os.environ.get("LEXIREAD_DATA_DIR") or (BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("LEXIREAD_UPLOAD_DIR") or (DATA_DIR / "uploads"))
DB_PATH = Path(os.environ.get("LEXIREAD_DB_PATH") or (DATA_DIR / "lexiread.db"))
OCR_SCRIPT = TOOLS_DIR / "windows_ocr.ps1"
PWA = bool(os.environ.get("LEXIREAD_PWA"))

for _dir in (DATA_DIR, UPLOAD_DIR):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Browser (Pyodide) builds mount these paths from a virtual filesystem;
        # a read-only package should not crash at import time.
        pass

APP_NAME = "LexiRead"
APP_TITLE = "LexiRead · 精读工坊"
HOST = os.environ.get("LEXIREAD_HOST", "127.0.0.1")
PORT = int(os.environ.get("LEXIREAD_PORT", "5057"))

DEFAULT_SETTINGS = {
    "ai": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "",
        "temperature": 0.2,
    },
    "learning": {
        "exam": "CET-4",
        "accent": "us",
        "voice_rate": 1.0,
    },
    "ocr": {
        "ai_vision": False,
    },
}

PROVIDER_PRESETS = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "vision_model": "",
        "hint": "性价比高，中文讲解自然",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "vision_model": "gpt-4o-mini",
        "hint": "需要可用的 OpenAI API Key",
    },
    {
        "id": "qwen",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "vision_model": "qwen-vl-plus",
        "hint": "阿里云百炼的兼容接口",
    },
    {
        "id": "zhipu",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "vision_model": "glm-4v-flash",
        "hint": "支持 GLM-4 系列",
    },
    {
        "id": "ollama",
        "name": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "vision_model": "qwen2.5vl:7b",
        "hint": "完全本地，需先启动 Ollama",
    },
    {
        "id": "custom",
        "name": "自定义",
        "base_url": "",
        "model": "",
        "vision_model": "",
        "hint": "任意 OpenAI 兼容服务",
    },
]
