"""Tiny HTTP server for keeping free hosts (e.g. Replit) awake via external pings.

Imported and started only when the process detects it is running on Replit
(env var `REPL_ID` is set automatically by Replit). Has no effect elsewhere.
"""
from __future__ import annotations

import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

log = logging.getLogger(__name__)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"alive")

    def log_message(self, *_args, **_kwargs) -> None:  # silence access log spam
        return


def _serve(port: int) -> None:
    try:
        HTTPServer(("0.0.0.0", port), _Handler).serve_forever()
    except Exception:  # noqa: BLE001
        log.exception("keep_alive server crashed")


def keep_alive() -> None:
    port = int(os.environ.get("PORT", "8080"))
    Thread(target=_serve, args=(port,), daemon=True).start()
    log.info("keep_alive HTTP server started on :%d", port)
