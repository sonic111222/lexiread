"""Serve dist_pwa/ locally (localhost is a secure context for service workers)."""
from __future__ import annotations

import http.server
import mimetypes
import os
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist_pwa"
PORT = int(os.environ.get("LEXIREAD_PWA_PORT", "8080"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Service-Worker-Allowed", "/")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    if not (DIST / "index.html").exists():
        print("dist_pwa 不存在，请先运行: python tools/build_pwa.py")
        return 1
    mimetypes.add_type("application/manifest+json", ".webmanifest")
    mimetypes.add_type("application/wasm", ".wasm")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("application/javascript", ".js")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as server:
        url = f"http://127.0.0.1:{PORT}/"
        print(f"LexiRead PWA: {url}")
        print("按 Ctrl+C 停止")
        if not os.environ.get("LEXIREAD_NO_BROWSER"):
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
