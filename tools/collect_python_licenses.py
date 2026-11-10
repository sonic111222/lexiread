"""Collect dependency license texts from a build virtualenv.

Usage:
    python tools/collect_python_licenses.py .venv-build

This is a maintenance helper for release packaging. It writes a combined text
file under LICENSES/ so the portable build can ship third-party notices.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "LICENSES" / "PYTHON_DEPENDENCIES.txt"

PACKAGES = [
    ("Flask", "flask"),
    ("Werkzeug", "werkzeug"),
    ("Jinja2", "jinja2"),
    ("MarkupSafe", "markupsafe"),
    ("itsdangerous", "itsdangerous"),
    ("click", "click"),
    ("blinker", "blinker"),
    ("requests", "requests"),
    ("urllib3", "urllib3"),
    ("certifi", "certifi"),
    ("charset-normalizer", "charset_normalizer"),
    ("idna", "idna"),
    ("Pillow", "pillow"),
    ("packaging", "packaging"),
    ("PyInstaller", "pyinstaller"),
    ("pyinstaller-hooks-contrib", "pyinstaller_hooks_contrib"),
    ("altgraph", "altgraph"),
    ("pefile", "pefile"),
    ("pywin32-ctypes", "pywin32_ctypes"),
]


def find_dist_info(site_packages: Path, normalized: str) -> Path | None:
    for path in site_packages.glob(f"{normalized}-*.dist-info"):
        return path
    return None


def license_files(dist_info: Path) -> list[Path]:
    base = dist_info / "licenses"
    candidates: list[Path] = []
    if base.exists():
        candidates.extend(sorted(p for p in base.rglob("*") if p.is_file()))
    candidates.extend(
        sorted(
            p
            for p in dist_info.iterdir()
            if p.is_file() and p.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE"))
        )
    )
    seen = set()
    output = []
    for path in candidates:
        key = path.name.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(path)
    return output


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    venv = Path(sys.argv[1]).resolve()
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.exists():
        print(f"site-packages not found: {site_packages}")
        return 1

    sections = []
    missing = []
    for display, normalized in PACKAGES:
        dist = find_dist_info(site_packages, normalized)
        if not dist:
            missing.append(display)
            continue
        files = license_files(dist)
        if not files:
            missing.append(display)
            continue
        chunks = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if text:
                chunks.append(f"--- {path.name} ---\n\n{text}")
        if chunks:
            sections.append(f"======================================================================\n{display} ({dist.name})\n======================================================================\n\n" + "\n\n".join(chunks))

    header = """LexiRead third-party Python dependency licenses
================================================

This file is generated from the packages installed in a clean build
environment. It is included in the portable Windows release. The packages are
not part of LexiRead's own MIT-licensed source code; each remains under its own
license.
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + "\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    if missing:
        print("missing license files for:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
