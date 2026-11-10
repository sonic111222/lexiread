"""Build the bundled ECDICT subset used by the offline dictionary.

Usage:
    python tools/build_ecdict_subset.py path/to/ecdict.csv

Download the source CSV from:
    https://github.com/skywind3000/ECDICT/blob/master/ecdict.csv

ECDICT is MIT licensed. Keep LICENSES/ECDICT.txt with any redistributed data.
The generated files are frequency-ordered, trimmed for app size, and contain
only the fields LexiRead needs.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "backend" / "data" / "ecdict_subset.json.gz"
OUT_WORDS = ROOT / "backend" / "data" / "words_frequency.txt"
LIMIT = 26000

TAG_MAP = {
    "zk": "中考",
    "gk": "高考",
    "cet4": "CET4",
    "cet6": "CET6",
    "ky": "考研",
    "ielts": "IELTS",
    "toefl": "TOEFL",
    "gre": "GRE",
    "gmat": "GMAT",
    "sat": "SAT",
}


def clean_text(value: str) -> str:
    value = (value or "").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    value = value.replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", value).strip()


def split_translation(value: str) -> list[str]:
    lines: list[str] = []
    for line in clean_text(value).splitlines():
        line = line.strip(" ;；")
        if not line or line.startswith("[网络]"):
            continue
        if len(line) > 220:
            line = line[:218].rstrip() + "…"
        lines.append(line)
        if len(lines) >= 4:
            break
    if not lines:
        first = clean_text(value).split("\n")[0].strip()
        if first:
            lines = [first[:220]]
    return lines


def tags_of(value: str) -> list[str]:
    tags: list[str] = []
    for token in re.split(r"[\s,;]+", (value or "").lower()):
        token = token.strip()
        mapped = TAG_MAP.get(token)
        if mapped and mapped not in tags:
            tags.append(mapped)
    return tags[:5]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    if not source.exists():
        print(f"CSV not found: {source}")
        return 1

    candidates = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            word = (row.get("word") or "").strip()
            if not word or len(word) > 32 or not re.fullmatch(r"[A-Za-z][A-Za-z' -]*[A-Za-z]", word):
                continue
            translation = (row.get("translation") or "").strip()
            if not translation:
                continue
            try:
                frq = int(row.get("frq") or 0)
                bnc = int(row.get("bnc") or 0)
            except ValueError:
                frq = bnc = 0
            if not frq and not bnc:
                continue
            candidates.append(
                (word, frq if frq > 0 else 10**9, bnc if bnc > 0 else 10**9, row)
            )

    candidates.sort(key=lambda item: (item[1], item[2], len(item[0])))
    selected = candidates[:LIMIT]
    entries: dict[str, dict] = {}
    tag_counts: Counter[str] = Counter()
    for word, _frq, _bnc, row in selected:
        key = word.lower()
        if key in entries:
            continue
        translations = split_translation(row.get("translation") or "")
        if not translations:
            continue
        tags = tags_of(row.get("tag") or "")
        tag_counts.update(tags)
        entry = {
            "word": word,
            "phonetic": (row.get("phonetic") or "").strip(),
            "translations": translations,
            "tags": tags,
        }
        exchange = (row.get("exchange") or "").strip()
        if exchange:
            entry["exchange"] = exchange
        entries[key] = entry

    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(payload)

    with OUT_WORDS.open("w", encoding="utf-8", newline="\n") as stream:
        for word, _frq, _bnc, _row in selected:
            if re.fullmatch(r"[a-z]+", word.lower()):
                stream.write(word.lower() + "\n")

    print(f"wrote {len(entries)} entries -> {OUT_JSON}")
    print(f"wrote word list -> {OUT_WORDS}")
    print(f"tag counts: {dict(tag_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
