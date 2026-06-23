#!/usr/bin/env python3
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

DEFAULT_PORT = 5050


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(start: int) -> int:
    for port in range(start, start + 20):
        if port_free(port):
            return port
    raise RuntimeError("Нет свободного порта")


def main() -> None:
    preferred = int(os.getenv("ZAMAN_PORT", os.getenv("JARVIS_PORT", str(DEFAULT_PORT))))
    port = pick_port(preferred)
    url = f"http://127.0.0.1:{port}/"
    if port != preferred:
        print(f"Порт {preferred} занят, использую {port}")
    print(f"ZamanAI: {url}")
    def open_browser() -> None:
        time.sleep(1.2)
        webbrowser.open(url)
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("server:app", host="127.0.0.1", port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)