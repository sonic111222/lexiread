"""Download the optional PWA vendor assets (Pyodide + Tesseract.js).

The assets are large and are intentionally kept out of git. Run this once
before ``python tools/build_pwa.py``:

    python tools/fetch_pwa_vendor.py

Network access is required. Pass ``--force`` to re-download existing files.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "pwa_vendor"

PYODIDE_VERSION = "0.29.5"
PYODIDE_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
TESSERACT_VERSION = "5.1.1"
TESSERACT_BASE = f"https://cdn.jsdelivr.net/npm/tesseract.js@{TESSERACT_VERSION}/dist/"
TESSERACT_CORE_BASE = "https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.0/"
LANG_BASE = "https://cdn.jsdelivr.net/npm/@tesseract.js-data/eng@1.0.0/4.0.0_best_int/"

FILES = [
    (PYODIDE_BASE + "pyodide.mjs", "pyodide/pyodide.mjs"),
    (PYODIDE_BASE + "pyodide.js", "pyodide/pyodide.js"),
    (PYODIDE_BASE + "pyodide.asm.js", "pyodide/pyodide.asm.js"),
    (PYODIDE_BASE + "pyodide.asm.wasm", "pyodide/pyodide.asm.wasm"),
    (PYODIDE_BASE + "python_stdlib.zip", "pyodide/python_stdlib.zip"),
    (PYODIDE_BASE + "pyodide-lock.json", "pyodide/pyodide-lock.json"),
    (
        PYODIDE_BASE + "sqlite3-1.0.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
        "pyodide/sqlite3-1.0.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
    ),
    (PYODIDE_BASE + "requests-2.32.4-py3-none-any.whl", "pyodide/requests-2.32.4-py3-none-any.whl"),
    (
        PYODIDE_BASE + "charset_normalizer-3.4.4-py3-none-any.whl",
        "pyodide/charset_normalizer-3.4.4-py3-none-any.whl",
    ),
    (PYODIDE_BASE + "idna-3.10-py3-none-any.whl", "pyodide/idna-3.10-py3-none-any.whl"),
    (PYODIDE_BASE + "urllib3-2.5.0-py3-none-any.whl", "pyodide/urllib3-2.5.0-py3-none-any.whl"),
    (PYODIDE_BASE + "certifi-2026.1.4-py3-none-any.whl", "pyodide/certifi-2026.1.4-py3-none-any.whl"),
    (TESSERACT_BASE + "tesseract.min.js", "tesseract/tesseract.min.js"),
    (TESSERACT_BASE + "worker.min.js", "tesseract/worker.min.js"),
    (TESSERACT_CORE_BASE + "tesseract-core-simd-lstm.wasm.js", "tesseract/tesseract-core-simd-lstm.wasm.js"),
    (TESSERACT_CORE_BASE + "tesseract-core-simd-lstm.wasm", "tesseract/tesseract-core-simd-lstm.wasm"),
    (LANG_BASE + "eng.traineddata.gz", "tesseract/lang/eng.traineddata.gz"),
]


def download(url: str, target: Path, force: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"skip  {target.relative_to(ROOT)}")
        return
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "LexiRead-PWA-builder/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            if not data:
                raise OSError("empty response")
            target.write_bytes(data)
            print(f"ok    {target.relative_to(ROOT)} ({len(data) / 1024 / 1024:.1f} MiB)")
            return
        except Exception as exc:  # noqa: BLE001 - network errors vary
            last_error = exc
            print(f"retry {attempt}/3 {url}: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise SystemExit(f"failed to download {url}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for url, relative in FILES:
        download(url, VENDOR / relative, force=args.force)
    total = sum(path.stat().st_size for path in VENDOR.rglob("*") if path.is_file())
    print(f"\nVendor ready: {VENDOR} ({total / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
