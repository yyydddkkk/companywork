from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Iterator

import httpx


BACKEND_DIR = Path(__file__).resolve().parents[1]


@contextmanager
def run_server(database_path: Path) -> Iterator[str]:
    port = _get_free_port()
    env = os.environ.copy()
    env['DATABASE_PATH'] = str(database_path)
    env['PROJECT_ROOT'] = str(BACKEND_DIR.parent)
    process = subprocess.Popen(
        [
            str(BACKEND_DIR / '.venv' / 'bin' / 'python'),
            '-m',
            'uvicorn',
            'app.main:app',
            '--host',
            '127.0.0.1',
            '--port',
            str(port),
        ],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f'http://127.0.0.1:{port}'
    try:
        _wait_for_server(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _wait_for_server(base_url: str) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            response = httpx.get(f'{base_url}/health', timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError('Server did not start in time.')


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])
