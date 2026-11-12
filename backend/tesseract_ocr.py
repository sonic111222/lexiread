"""Optional local English OCR via Tesseract.

Tesseract is not a Python dependency: the app looks for a portable runtime in
``runtime/tesseract``, on PATH, or in the active conda environment. When it is
available it is preferred over the Windows OCR engine for English photos,
because Windows OCR quality depends heavily on the installed language pack.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from functools import lru_cache
from pathlib import Path

from PIL import Image

from .config import BASE_DIR, RESOURCE_DIR, UPLOAD_DIR


class TesseractError(RuntimeError):
    pass


def _executable_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("LEXIREAD_TESSERACT") or os.environ.get("TESSERACT_CMD")
    if configured:
        candidates.append(Path(configured))
    for base in (BASE_DIR, RESOURCE_DIR):
        candidates.append(base / "runtime" / "tesseract" / "tesseract.exe")
        candidates.append(base / "tools" / "tesseract" / "tesseract.exe")
    found = shutil.which("tesseract")
    if found:
        candidates.append(Path(found))
    candidates.append(Path(sys.prefix) / "Library" / "bin" / "tesseract.exe")
    candidates.append(Path(sys.prefix) / "Scripts" / "tesseract.exe")
    return candidates


@lru_cache(maxsize=1)
def executable() -> Path | None:
    for candidate in _executable_candidates():
        if candidate.is_file():
            return candidate
    return None


def _tessdata(exe: Path) -> Path | None:
    configured = os.environ.get("TESSDATA_PREFIX")
    if configured and Path(configured).is_dir():
        return Path(configured)
    for candidate in (exe.parent / "tessdata", exe.parent.parent / "share" / "tessdata"):
        if candidate.is_dir():
            return candidate
    return None


def _env(exe: Path) -> dict[str, str]:
    env = dict(os.environ)
    data = _tessdata(exe)
    if data:
        env["TESSDATA_PREFIX"] = str(data)
    env.setdefault("OMP_THREAD_LIMIT", "1")
    return env


def _run(args: list[str], exe: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(exe), *args],
        capture_output=True,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(exe),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


@lru_cache(maxsize=1)
def status() -> dict:
    exe = executable()
    if not exe:
        return {"available": False, "version": "", "languages": []}
    try:
        version = _run(["--version"], exe, timeout=15)
        languages = _run(["--list-langs"], exe, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "version": "", "languages": [], "message": str(exc)}
    tags = [
        line.strip()
        for line in (languages.stdout or "").splitlines()[1:]
        if line.strip() and " " not in line.strip()
    ]
    first_line = (version.stdout or "").splitlines()[0] if version.stdout else ""
    return {
        "available": version.returncode == 0,
        "version": first_line.strip(),
        "languages": tags,
        "path": str(exe),
    }


def available() -> bool:
    data = status()
    return bool(data.get("available") and "eng" in data.get("languages", []))


def _heading_y(tsv: str) -> int:
    """Find the vertical position of a short 'Passage N' heading."""
    lines: dict[tuple[str, str, str], dict] = {}
    try:
        rows = csv.DictReader(io.StringIO(tsv), delimiter="\t")
        for row in rows:
            if row.get("level") != "5":
                continue
            key = (row.get("block_num", ""), row.get("par_num", ""), row.get("line_num", ""))
            entry = lines.setdefault(key, {"top": 10**9, "text": []})
            entry["top"] = min(entry["top"], int(row.get("top") or 0))
            if (row.get("text") or "").strip():
                entry["text"].append(row["text"].strip())
    except (ValueError, TypeError):
        return 0
    candidates: list[int] = []
    for entry in lines.values():
        text = " ".join(entry["text"]).strip()
        if not text or len(text) > 42:
            continue
        if re.search(r"(?i)\bpassa\w*\s*[1-9]\b", text) or re.search(r"(?i)^reading comprehension$", text):
            candidates.append(entry["top"])
    return min(candidates) if candidates else 0


def recognize(image_path: Path, psm: int = 6, autocrop: bool = True) -> dict:
    exe = executable()
    if not exe or not available():
        raise TesseractError("没有找到可用的 Tesseract 英文 OCR 运行时。")
    started = time.perf_counter()
    crop_path: Path | None = None
    crop_y = 0
    try:
        if autocrop:
            try:
                probe = _run(
                    [
                        str(image_path), "stdout", "-l", "eng", "--oem", "1",
                        "--psm", str(psm), "-c", "tessedit_create_tsv=1",
                    ],
                    exe,
                    timeout=90,
                )
                crop_y = _heading_y(probe.stdout or "")
                if crop_y:
                    with Image.open(image_path) as image:
                        if image.height * 0.06 < crop_y < image.height * 0.8:
                            crop_path = UPLOAD_DIR / f".tess_crop_{uuid.uuid4().hex}.png"
                            image.crop((0, max(0, crop_y - 30), image.width, image.height)).save(
                                crop_path, "PNG", compress_level=1
                            )
            except (OSError, subprocess.SubprocessError):
                crop_path = None

        targets = [crop_path, image_path] if crop_path else [image_path]
        proc = None
        text = ""
        for target in targets:
            proc = _run(
                [str(target), "stdout", "-l", "eng", "--oem", "1", "--psm", str(psm)],
                exe,
                timeout=90,
            )
            text = (proc.stdout or "").replace("\f", "\n")
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if proc.returncode == 0 and len(re.findall(r"[A-Za-z]", text)) >= 10:
                break
    except subprocess.TimeoutExpired as exc:
        raise TesseractError("Tesseract OCR 超时，请换一张更小的图片。") from exc
    except OSError as exc:
        raise TesseractError(f"无法启动 Tesseract OCR：{exc}") from exc
    finally:
        if crop_path:
            crop_path.unlink(missing_ok=True)

    if proc is None or proc.returncode != 0:
        detail = (proc.stderr or "").strip().replace("\n", " ") if proc else ""
        raise TesseractError(f"Tesseract OCR 运行失败：{detail[:300] or '未知错误'}")
    if len(re.findall(r"[A-Za-z]", text)) < 10:
        raise TesseractError("Tesseract 没有识别出足够的英文。")
    return {
        "text": text,
        "meta": {
            "engine": "Tesseract OCR",
            "language": "eng",
            "psm": psm,
            "cropped": bool(crop_path),
            "crop_y": crop_y if crop_path else 0,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    }
