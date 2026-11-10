"""Local OCR powered by the OCR engine built into Windows."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Optional

from PIL import Image, ImageFilter, ImageOps

from .config import BUNDLED_DATA_DIR, OCR_SCRIPT, UPLOAD_DIR

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MAX_IMAGE_SIDE = 2600
MIN_OCR_WIDTH = 1500
# Common-word list derived from ECDICT (MIT). See backend/data/ECDICT_LICENSE.txt.
WORD_LIST_PATH = BUNDLED_DATA_DIR / "words_frequency.txt"
DIGIT_LOOKALIKES = {"0": "o", "1": "li", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"}


class OcrError(RuntimeError):
    pass


@dataclass
class OcrLine:
    text: str
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


def _powershell() -> Optional[str]:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def engine_status() -> dict:
    ps = _powershell()
    if not ps:
        return {"available": False, "engine": "Windows OCR", "languages": [], "message": "当前系统不是 Windows，或找不到 PowerShell。"}
    try:
        code = (
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
            "[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]|Out-Null;"
            "[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages|"
            "ForEach-Object{$_.LanguageTag}"
        )
        proc = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-Command", code],
            capture_output=True,
            timeout=20,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        langs = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        if proc.returncode == 0 and langs:
            return {
                "available": True,
                "engine": "Windows OCR",
                "languages": langs,
                "message": "使用 Windows 本机 OCR 识别，图片不会上传。",
            }
        return {
            "available": False,
            "engine": "Windows OCR",
            "languages": [],
            "message": "未检测到 Windows OCR 语言组件，请在系统设置中添加语言。",
        }
    except Exception as exc:  # pragma: no cover - depends on host
        return {"available": False, "engine": "Windows OCR", "languages": [], "message": f"OCR 状态检查失败：{exc}"}


def _safe_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXTENSIONS else ".png"


def normalize_image(source_path: Path, original_name: str = "") -> tuple[Path, str]:
    """Orient, downscale and save a browser-friendly copy of the upload."""
    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA") and image.getextrema()[-1][0] < 255:
                background = Image.new("RGB", image.size, (255, 255, 255))
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")
            if max(image.size) > MAX_IMAGE_SIDE:
                image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
            name = f"{uuid.uuid4().hex}.png"
            target = UPLOAD_DIR / name
            image.save(target, "PNG", optimize=True)
            return target, f"/api/uploads/{name}"
    except Exception as exc:
        raise OcrError("无法读取图片，请使用 PNG、JPG 或 WebP 格式。") from exc


def _prepare_variants(image_path: Path) -> list[tuple[str, Path]]:
    variants: list[tuple[str, Path]] = []
    with Image.open(image_path) as image:
        base = image.convert("RGB")
        if base.width < MIN_OCR_WIDTH:
            scale = min(2.5, max(1.5, MIN_OCR_WIDTH / max(base.width, 1)))
            base = base.resize(
                (int(base.width * scale), int(base.height * scale)),
                Image.Resampling.LANCZOS,
            )
        elif base.width > MAX_IMAGE_SIDE:
            base.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)

        enhanced = ImageOps.autocontrast(base.convert("L"), cutoff=0.5)
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3))
        enhanced_path = UPLOAD_DIR / f".ocr_{uuid.uuid4().hex}_clean.png"
        enhanced.save(enhanced_path, "PNG", optimize=True)
        variants.append(("clean", enhanced_path))

        gray = base.convert("L")
        # Dark-background screenshots benefit from inversion.
        stats = gray.resize((max(1, gray.width // 20), max(1, gray.height // 20))).convert("L")
        mean = sum(stats.getdata()) / max(1, len(stats.getdata()))
        if mean < 100:
            gray = ImageOps.invert(gray)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        raw_path = UPLOAD_DIR / f".ocr_{uuid.uuid4().hex}_raw.png"
        gray.save(raw_path, "PNG", optimize=True)
        variants.append(("raw", raw_path))
    return variants


def _run_windows_ocr(image_path: Path, timeout: int = 90) -> dict:
    ps = _powershell()
    if not ps:
        raise OcrError("找不到 PowerShell，无法调用 Windows OCR。")
    out_path = UPLOAD_DIR / f".ocr_{uuid.uuid4().hex}.json"
    try:
        proc = subprocess.run(
            [
                ps,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(OCR_SCRIPT),
                "-ImagePath",
                str(image_path),
                "-OutputPath",
                str(out_path),
            ],
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise OcrError(f"Windows OCR 运行失败：{detail[:500] or '未知错误'}")
        if not out_path.exists():
            raise OcrError("OCR 没有返回结果，请重试。")
        payload = json.loads(out_path.read_text(encoding="utf-8-sig"))
        return payload
    finally:
        out_path.unlink(missing_ok=True)


def _line_boxes(payload: dict) -> list[OcrLine]:
    lines: list[OcrLine] = []
    for raw in payload.get("lines", []):
        text = re.sub(r"\s+", " ", str(raw.get("text", ""))).strip()
        if not text:
            continue
        words = raw.get("words") or []
        if words:
            x = min(float(word.get("x", 0)) for word in words)
            y = min(float(word.get("y", 0)) for word in words)
            right = max(float(word.get("x", 0)) + float(word.get("w", 0)) for word in words)
            bottom = max(float(word.get("y", 0)) + float(word.get("h", 0)) for word in words)
            height = max(1.0, bottom - y)
            lines.append(OcrLine(text, x, y, right - x, height))
        else:
            lines.append(OcrLine(text, 0, len(lines) * 40.0, 600, 24))
    lines.sort(key=lambda line: (round(line.y / 8), line.x))
    return lines


def _ocr_score(payload: dict) -> float:
    text = " ".join(str(line.get("text", "")) for line in payload.get("lines", []))
    tokens = re.findall(r"[A-Za-z]{2,}", text)
    if not tokens:
        return 0.0
    common = {
        "the", "and", "to", "of", "in", "is", "are", "that", "for", "it", "as", "with",
        "on", "was", "be", "this", "by", "not", "or", "from", "have", "but", "they",
        "you", "we", "what", "which", "when", "why", "how", "questions", "answer",
    }
    common_hits = sum(1 for token in tokens if token.lower() in common)
    # Reward real words and penalise stray one-character OCR noise.
    noise = len(re.findall(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])", text))
    return len(tokens) + common_hits * 2 - noise * 0.4


@lru_cache(maxsize=1)
def _common_words() -> frozenset[str]:
    try:
        words = WORD_LIST_PATH.read_text(encoding="utf-8").splitlines()
        return frozenset(word.strip().lower() for word in words if word.strip().isalpha())
    except OSError:
        return frozenset()


def _fix_digit_confusions(text: str) -> str:
    """Correct OCR tokens such as t0, 0f or th1s using the frequency list."""
    words = _common_words()
    if not words:
        return text

    def repl(match: re.Match) -> str:
        token = match.group(0)
        if not re.search(r"\d", token) or not re.search(r"[A-Za-z]", token) or token.lower() in words:
            return token
        options = [DIGIT_LOOKALIKES.get(char, char) for char in token]
        for candidate_chars in product(*options):
            candidate = "".join(candidate_chars)
            if candidate.lower() in words:
                if token[:1].isupper():
                    return candidate[:1].upper() + candidate[1:]
                return candidate
        return token

    return re.sub(r"\b[A-Za-z0-9]*\d[A-Za-z0-9]*\b", repl, text)


def _fix_split_words(text: str) -> str:
    """Merge OCR-split words like 'eve ry' into 'every' conservatively."""
    words = _common_words()
    if not words:
        return text

    for _ in range(3):
        matches = list(re.finditer(r"[A-Za-z]+", text))
        output = []
        last = 0
        changed = False
        index = 0
        while index < len(matches):
            current = matches[index]
            if index + 1 < len(matches):
                following = matches[index + 1]
                between = text[current.end(): following.start()]
                combined = (current.group(0) + following.group(0)).lower()
                if (
                    between.isspace()
                    and len(following.group(0)) <= 3
                    and following.group(0).lower() not in words
                    and combined in words
                ):
                    output.append(text[last: current.start()])
                    output.append(current.group(0) + following.group(0))
                    last = following.end()
                    changed = True
                    index += 2
                    continue
            index += 1
        output.append(text[last:])
        new_text = "".join(output)
        if not changed:
            break
        text = new_text
    return text


def _fix_ocr_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[ \t]+", " ", text).strip()
    # Conservative fixes for the most common OCR confusions in English tests.
    text = re.sub(r"\bt0\b", "to", text)
    text = re.sub(r"\bT0\b", "To", text)
    text = re.sub(r"\btO\b", "to", text)
    text = re.sub(r"\bTO\b", "to", text)
    text = re.sub(r"\biS\b", "is", text)
    text = re.sub(r"\bll\b", "It", text)
    text = re.sub(r"__(?:\s*_\s*)+", "______", text)
    text = re.sub(r"(\d{1,2})\s*[·•∙]\s*", r"\1. ", text)
    text = re.sub(r"^([A-D])\s*[,，、]\s*", r"\1. ", text)
    text = _fix_digit_confusions(text)
    text = _fix_split_words(text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def _is_question_start(text: str) -> bool:
    return bool(re.match(r"^\s*(?:Q\s*)?\d{1,2}\s*[.)、:]\s*", text, re.I))


def _is_option_start(text: str) -> bool:
    return bool(re.match(r"^\s*(?:\(?[A-D]\)?[.)、:])\s*", text, re.I))


def _is_heading(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:passage|reading comprehension|directions?|part\s+[ivx\d]+|section\s+[a-z]|questions?\s+\d)",
            text,
            re.I,
        )
    )


def reconstruct_text(payload: dict) -> tuple[str, dict]:
    lines = _line_boxes(payload)
    if not lines:
        return "", {"line_count": 0, "paragraph_count": 0, "language": payload.get("language", "")}

    cleaned = [(line, _fix_ocr_text(line.text)) for line in lines]
    cleaned = [(line, text) for line, text in cleaned if text]
    heights = [line.h for line, _ in cleaned if line.h > 0]
    median_h = sorted(heights)[len(heights) // 2] if heights else 24.0
    max_right = max((line.x + line.w for line, _ in cleaned), default=1)
    min_left = min((line.x for line, _ in cleaned), default=0)
    content_width = max(1, max_right - min_left)

    paragraphs: list[str] = []
    current = ""
    previous: Optional[OcrLine] = None

    for line, text in cleaned:
        if not current:
            current = text
            previous = line
            continue

        gap = line.y - (previous.y + previous.h)
        new_para = False
        if gap > max(median_h * 1.25, 14):
            new_para = True
        elif _is_heading(current):
            new_para = True
        elif _is_question_start(text) or _is_option_start(text) or _is_heading(text):
            new_para = True
        elif _is_question_start(current[-160:]):
            # Keep a question stem together, but not its options.
            if _is_option_start(text):
                new_para = True
        elif re.search(r"[.!?。！？][\"')\]]?$", current) and re.match(r"^[A-Z\"'(]", text):
            previous_width = previous.w if previous else 0
            indented = line.x > min_left + median_h * 1.1
            short_line = previous_width < content_width * 0.72
            if short_line and (indented or gap > median_h * 0.35):
                new_para = True

        if new_para:
            paragraphs.append(current.strip())
            current = text
        else:
            if current.endswith("-") and text[:1].islower():
                current = current[:-1] + text
            else:
                current = f"{current} {text}"
        previous = line

    if current.strip():
        paragraphs.append(current.strip())

    # Drop obvious page furniture.
    filtered = []
    for para in paragraphs:
        if re.fullmatch(r"(?:page\s*)?\d+\s*(?:/|of|共)?\s*\d*", para, re.I):
            continue
        if re.fullmatch(r"第\s*\d+\s*页.*", para):
            continue
        filtered.append(para)

    text = "\n\n".join(filtered)
    return text, {
        "line_count": len(cleaned),
        "paragraph_count": len(filtered),
        "language": payload.get("language", ""),
        "image_width": payload.get("width"),
        "image_height": payload.get("height"),
    }


def recognize(image_path: Path) -> dict:
    started = time.perf_counter()
    variants = _prepare_variants(image_path)
    best_payload: Optional[dict] = None
    best_score = -1.0
    errors: list[str] = []
    try:
        for _name, variant in variants:
            try:
                payload = _run_windows_ocr(variant)
                score = _ocr_score(payload)
                if score > best_score:
                    best_payload = payload
                    best_score = score
            except Exception as exc:
                errors.append(str(exc))
    finally:
        for _name, variant in variants:
            variant.unlink(missing_ok=True)

    if not best_payload or best_score <= 0:
        message = errors[0] if errors else "没有识别到文字，请换一张更清晰、文字更完整的图片。"
        raise OcrError(message)

    text, meta = reconstruct_text(best_payload)
    if len(re.findall(r"[A-Za-z]", text)) < 10:
        raise OcrError("图片中的英文太少，未能识别出可用题目。请确认图片清晰并包含完整文字。")
    meta["duration_ms"] = int((time.perf_counter() - started) * 1000)
    meta["engine"] = "Windows OCR"
    return {"text": text, "meta": meta}


def save_upload(file_storage) -> tuple[Path, str, str]:
    original_name = file_storage.filename or "question.png"
    ext = _safe_extension(original_name)
    temp_path = UPLOAD_DIR / f".upload_{uuid.uuid4().hex}{ext}"
    file_storage.save(temp_path)
    try:
        normalized, preview_url = normalize_image(temp_path, original_name)
    finally:
        temp_path.unlink(missing_ok=True)
    return normalized, preview_url, original_name
