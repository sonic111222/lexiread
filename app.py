"""LexiRead entry point.

Run with:  python app.py
"""
from __future__ import annotations

import mimetypes
import os
import socket
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from backend import ai
from backend.api import api
from backend.config import PORT, STATIC_DIR
from backend.storage import init_db

# Windows can report .js/.css as text/plain in the registry; module scripts and
# stylesheets require correct MIME types, especially with nosniff enabled.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/webp", ".webp")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config.update(
        MAX_CONTENT_LENGTH=30 * 1024 * 1024,
        JSON_AS_ASCII=False,
        SECRET_KEY="lexiread-local-only",
    )
    app.register_blueprint(api, url_prefix="/api")

    @app.get("/")
    def index():
        response = send_from_directory(STATIC_DIR, "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(STATIC_DIR, "favicon.svg", mimetype="image/svg+xml")

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith("/static/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "图片太大，请压缩到 30MB 以内。", "code": "too_large"}), 413
        return "File too large", 413

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "接口不存在。", "code": "not_found"}), 404
        if request.path.startswith("/static/"):
            return "Not found", 404
        # Hash routing means unknown page paths can safely return the app shell.
        response = send_from_directory(STATIC_DIR, "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Unhandled error: %s", error)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "服务器内部错误，请查看启动窗口的日志。", "code": "server_error"}), 500
        return "Internal server error", 500

    return app


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_port(start: int) -> int:
    for offset in range(20):
        candidate = start + offset
        if _port_available(candidate):
            return candidate
    raise RuntimeError("找不到可用端口，请关闭其他程序后重试。")


def _open_browser(url: str) -> None:
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    init_db()
    app = create_app()
    port = _find_port(PORT)
    url = f"http://127.0.0.1:{port}"
    status = ai.status()
    print("")
    print("  LexiRead · 精读工坊")
    print("  " + "-" * 42)
    print(f"  打开浏览器访问: {url}")
    print(f"  AI 解析: {'已连接' if status['configured'] else '未配置（本地功能可正常使用）'}")
    print("  按 Ctrl+C 停止服务")
    print("")
    if not os.environ.get("LEXIREAD_NO_BROWSER"):
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
