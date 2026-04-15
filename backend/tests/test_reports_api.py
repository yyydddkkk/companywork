import io
from pathlib import Path
import time

import httpx

from conftest import run_server


def _wait_job_completed(base_url: str, job_id: str, timeout: float = 12.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = httpx.get(f'{base_url}/api/jobs/{job_id}', timeout=5)
        assert response.status_code == 200
        payload = response.json()
        if payload['status'] == 'completed':
            return payload
        assert payload['status'] != 'failed'
        time.sleep(0.2)
    raise AssertionError('job did not complete in time')


def test_analyze_and_get_bug_report(tmp_path: Path) -> None:
    payload = {
        'source': 'inline',
        'issues': [
            {
                'external_id': '1',
                'title': 'Crash when opening settings page',
                'body': 'Users see a stack trace and exception after clicking settings.',
            }
        ],
    }

    with run_server(tmp_path / 'reports.db') as base_url:
        response = httpx.post(f'{base_url}/api/issues/analyze', json=payload, timeout=10)
        assert response.status_code == 200
        report_id = response.json()['report_id']
        status = _wait_job_completed(base_url, report_id)
        assert status['report_ready'] is True

        report_response = httpx.get(f'{base_url}/api/reports/{report_id}', timeout=10)
        assert report_response.status_code == 200
        body = report_response.json()

    assert body['report_id'] == report_id
    assert body['diagnosis']['type'] == 'Bug'
    assert body['requires_human'] is False
    assert len(body['agent_trace']) == 3
    assert '<div id="agent-trace">' in body['html_report']
    assert '<section id="diagnosis">' in body['html_report']
    assert '<pre id="reproduce-code">' in body['html_report']


def test_html_contract_for_docs_report(tmp_path: Path) -> None:
    payload = {
        'source': 'inline',
        'issues': [
            {
                'external_id': '2',
                'title': 'Docs update needed for setup guide',
                'body': 'The README still references Python 3.10 and old screenshots.',
            }
        ],
    }

    with run_server(tmp_path / 'docs.db') as base_url:
        report_id = httpx.post(f'{base_url}/api/issues/analyze', json=payload, timeout=10).json()['report_id']
        _wait_job_completed(base_url, report_id)
        html_report = httpx.get(f'{base_url}/api/reports/{report_id}', timeout=10).json()['html_report']

    assert '<div id="agent-trace">' in html_report
    assert '<section id="diagnosis">' in html_report
    assert '<pre id="reproduce-code">' not in html_report


def test_human_feedback_and_rerun_debugger(tmp_path: Path) -> None:
    payload = {
        'source': 'inline',
        'issues': [
            {
                'external_id': '3',
                'title': 'Intermittent UI freeze when opening dashboard',
                'body': 'Cannot reproduce deterministically. Sometimes only happens after a long idle period.',
            }
        ],
    }

    with run_server(tmp_path / 'human.db') as base_url:
        report_id = httpx.post(f'{base_url}/api/issues/analyze', json=payload, timeout=10).json()['report_id']
        _wait_job_completed(base_url, report_id)
        first_report = httpx.get(f'{base_url}/api/reports/{report_id}', timeout=10).json()
        assert first_report['requires_human'] is True

        feedback_response = httpx.post(
            f'{base_url}/api/reports/{report_id}/human-feedback',
            json={'human_note': 'It always happens after the browser tab sleeps for 30 minutes.'},
            timeout=10,
        )
        assert feedback_response.status_code == 200
        assert feedback_response.json()['human_note'].startswith('It always happens')

        rerun_response = httpx.post(f'{base_url}/api/reports/{report_id}/rerun-debugger', timeout=10)
        assert rerun_response.status_code == 200
        rerun_data = rerun_response.json()
        assert rerun_data['rerun_count'] == 1
        assert rerun_data['requires_human'] is False

        updated_report = httpx.get(f'{base_url}/api/reports/{report_id}', timeout=10).json()

    assert updated_report['requires_human'] is False
    assert len(updated_report['agent_trace']) == 4
    assert updated_report['diagnosis']['reproduce_code'].startswith('def reproduce_issue')


def test_upload_json_creates_report(tmp_path: Path) -> None:
    upload = io.BytesIO(
        b'[{"external_id": "4", "title": "Feature request: export trace", "body": "Need CSV export for traces."}]'
    )

    with run_server(tmp_path / 'upload.db') as base_url:
        response = httpx.post(
            f'{base_url}/api/issues/analyze/upload',
            files={'file': ('issues.json', upload.getvalue(), 'application/json')},
            timeout=10,
        )
        assert response.status_code == 200
        report_id = response.json()['report_id']
        _wait_job_completed(base_url, report_id)
        report = httpx.get(f'{base_url}/api/reports/{report_id}', timeout=10).json()

    assert report['diagnosis']['type'] == 'Feature'


def test_github_issue_without_fetch_returns_400(tmp_path: Path) -> None:
    payload = {
        'source': 'github',
        'issues': [],
        'github': {
            'owner': 'langchain-ai',
            'repo': 'langchain',
            'issue_number': 1,
        },
    }

    with run_server(tmp_path / 'github-missing-title.db') as base_url:
        response = httpx.post(f'{base_url}/api/issues/analyze', json=payload, timeout=10)

    assert response.status_code == 400
    assert 'ENABLE_GITHUB_FETCH=true' in response.text


def test_upload_invalid_extension_returns_400(tmp_path: Path) -> None:
    with run_server(tmp_path / 'upload-invalid.db') as base_url:
        response = httpx.post(
            f'{base_url}/api/issues/analyze/upload',
            files={'file': ('issues.txt', b'not a supported format', 'text/plain')},
            timeout=10,
        )

    assert response.status_code == 400
    assert 'supports .json or .csv' in response.text
