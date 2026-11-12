"""Build the installable LexiRead PWA.

Run after ``python tools/fetch_pwa_vendor.py``:

    python tools/build_pwa.py

Output: ``dist_pwa/``. Serve it over HTTPS (or localhost) for install/offline.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist_pwa"
VENDOR = ROOT / "pwa_vendor"
STATIC = ROOT / "static"
PWA = ROOT / "pwa"
ASSETS = ROOT / "assets"
VERSION = "1.0.0"
BUILD_ID = ""
CACHE_NAME = ""

BACKEND_FILES = [
    "backend/__init__.py",
    "backend/analyzer.py",
    "backend/ai.py",
    "backend/config.py",
    "backend/dictionary.py",
    "backend/samples.py",
    "backend/storage.py",
    "backend/ocr_text.py",
    "backend/providers/__init__.py",
    "backend/providers/base.py",
    "backend/providers/ecdict.py",
    "backend/providers/wiktionary.py",
    "pwa_bridge/__init__.py",
    "pwa_bridge/service.py",
]
DATA_FILES = [
    "backend/data/ecdict_subset.json.gz",
    "backend/data/words_frequency.txt",
    "backend/data/ECDICT_LICENSE.txt",
    "backend/data/README.md",
]


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def build_backend_zip() -> Path:
    target = DIST / "backend.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in BACKEND_FILES + DATA_FILES:
            path = ROOT / relative
            if path.exists():
                archive.write(path, relative)
    return target


def rewrite_index() -> None:
    source = (STATIC / "index.html").read_text(encoding="utf-8-sig")
    source = source.replace('href="/static/', 'href="./static/')
    source = source.replace('src="/static/', 'src="./static/')
    source = source.replace("?v=1.1.4", f"?v={BUILD_ID}")
    head_additions = """  <link rel="manifest" href="./manifest.webmanifest">
  <link rel="apple-touch-icon" href="./icons/apple-touch-icon.png">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="LexiRead">
  <script>window.__LEXIREAD_PWA__ = true;</script>
  <script src="./vendor/tesseract/tesseract.min.js"></script>
"""
    source = source.replace("</head>", head_additions + "</head>")
    source = source.replace(
        "</body>",
        """<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
}
</script>
</body>""",
    )
    (DIST / "index.html").write_text(source, encoding="utf-8")


def make_icons() -> None:
    icons = DIST / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    logo = Image.open(ASSETS / "lexiread.png").convert("RGBA")
    for size in (192, 512):
        icon = logo.resize((size, size), Image.Resampling.LANCZOS)
        icon.save(icons / f"icon-{size}.png", "PNG", optimize=True)
    apple = logo.resize((180, 180), Image.Resampling.LANCZOS)
    apple.save(icons / "apple-touch-icon.png", "PNG", optimize=True)
    # Maskable icon: keep the logo inside the safe zone on the brand color.
    size = 512
    canvas = Image.new("RGBA", (size, size), (24, 63, 53, 255))
    inner = logo.copy()
    inner.thumbnail((int(size * 0.72), int(size * 0.72)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(inner, ((size - inner.width) // 2, (size - inner.height) // 2))
    canvas.convert("RGB").save(icons / "maskable-512.png", "PNG", optimize=True)


def write_manifest() -> None:
    manifest = {
        "name": "LexiRead · 精读工坊",
        "short_name": "LexiRead",
        "description": "把一张英语题图，读成一堂课。本机 OCR、点词学习、生词本与可选 AI 精讲。",
        "lang": "zh-CN",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#f6f2e8",
        "theme_color": "#183f35",
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {
                "src": "icons/maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    (DIST / "manifest.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_service_worker() -> None:
    vendor_files = [
        "vendor/pyodide/pyodide.js",
        "vendor/pyodide/pyodide.asm.js",
        "vendor/pyodide/pyodide.asm.wasm",
        "vendor/pyodide/python_stdlib.zip",
        "vendor/pyodide/pyodide-lock.json",
        "vendor/pyodide/sqlite3-1.0.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
        "vendor/pyodide/requests-2.32.4-py3-none-any.whl",
        "vendor/pyodide/charset_normalizer-3.4.4-py3-none-any.whl",
        "vendor/pyodide/idna-3.10-py3-none-any.whl",
        "vendor/pyodide/urllib3-2.5.0-py3-none-any.whl",
        "vendor/pyodide/certifi-2026.1.4-py3-none-any.whl",
        "vendor/tesseract/tesseract.min.js",
        "vendor/tesseract/worker.min.js",
        "vendor/tesseract/tesseract-core-simd-lstm.wasm.js",
        "vendor/tesseract/tesseract-core-simd-lstm.wasm",
        "vendor/tesseract/lang/eng.traineddata.gz",
    ]
    assets = [
        "./",
        "./index.html",
        "./manifest.webmanifest",
        "./backend.zip",
        "./static/css/app.css",
        "./static/js/app.js",
        "./static/js/api.js",
        "./static/js/bridge.js",
        "./static/js/pyodide-worker.js",
        "./static/favicon.svg",
        "./icons/icon-192.png",
        "./icons/icon-512.png",
        "./icons/maskable-512.png",
        "./icons/apple-touch-icon.png",
        *[f"./{path}" for path in vendor_files],
    ]
    worker = f"""/* Generated by tools/build_pwa.py. */
const CACHE = "{CACHE_NAME}";
const ASSETS = {json.dumps(assets, ensure_ascii=False)};

self.addEventListener("install", (event) => {{
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (event) => {{
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === "navigate") {{
    event.respondWith(
      caches.match("./index.html").then((cached) => cached || fetch(request))
    );
    return;
  }}
  event.respondWith(
    caches.match(request).then((cached) => {{
      if (cached) return cached;
      return fetch(request).then((response) => {{
        if (response.ok) {{
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {{}});
        }}
        return response;
      }});
    }})
  );
}});
"""
    (DIST / "sw.js").write_text(worker, encoding="utf-8")


def main() -> int:
    if not (VENDOR / "pyodide" / "pyodide.asm.wasm").exists():
        raise SystemExit("缺少 pwa_vendor，请先运行: python tools/fetch_pwa_vendor.py")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    copy_tree(STATIC, DIST / "static")
    shutil.copy2(PWA / "js" / "api-pwa.js", DIST / "static" / "js" / "api.js")
    shutil.copy2(PWA / "js" / "bridge.js", DIST / "static" / "js" / "bridge.js")
    shutil.copy2(PWA / "js" / "pyodide-worker.js", DIST / "static" / "js" / "pyodide-worker.js")
    copy_tree(VENDOR, DIST / "vendor")
    backend_zip = build_backend_zip()
    global BUILD_ID, CACHE_NAME
    BUILD_ID = hashlib.sha256(
        (ROOT / "static" / "index.html").read_bytes()
        + (ROOT / "static" / "css" / "app.css").read_bytes()
        + (ROOT / "static" / "js" / "app.js").read_bytes()
        + (PWA / "js" / "bridge.js").read_bytes()
        + (PWA / "js" / "api-pwa.js").read_bytes()
        + (PWA / "js" / "pyodide-worker.js").read_bytes()
        + backend_zip.read_bytes()
        + VERSION.encode()
    ).hexdigest()[:10]
    CACHE_NAME = f"lexiread-pwa-{VERSION}-{BUILD_ID}"
    rewrite_index()
    make_icons()
    write_manifest()
    write_service_worker()
    total = sum(path.stat().st_size for path in DIST.rglob("*") if path.is_file())
    print(f"PWA built: {DIST} ({total / 1024 / 1024:.1f} MiB)")
    print("Open http://localhost:8080 after: python pwa/serve_pwa.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
