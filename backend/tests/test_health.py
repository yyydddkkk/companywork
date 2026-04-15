from pathlib import Path

import httpx

from conftest import run_server


def test_health_endpoint_returns_ok(tmp_path: Path) -> None:
    with run_server(tmp_path / 'health.db') as base_url:
        response = httpx.get(f'{base_url}/health', timeout=5)
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
