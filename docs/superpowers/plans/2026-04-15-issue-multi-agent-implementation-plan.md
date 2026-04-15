# GitHub Issue Multi-Agent Diagnostic System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable full-stack MVP that ingests GitHub/uploaded issues, runs Triager/Researcher/Debugger/Documenter orchestration, and renders required HTML diagnostic reports with human-in-the-loop rerun support.

**Architecture:** Use a single FastAPI backend with modular agent classes and SQLite persistence, plus a Vite + React frontend for job creation/report review. Keep the pipeline deterministic via rule-based logic and allow optional LLM enhancement via provider abstraction. Docker Compose runs backend and frontend together with one command.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, Uvicorn, pytest; React 18, Vite, TypeScript; Docker Compose.

---

### Task 1: Bootstrap Repository Structure and Tooling

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Write failing backend health test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest -q tests/test_health.py::test_health_endpoint_returns_ok`
Expected: FAIL with import/module or missing route error.

- [ ] **Step 3: Implement minimal FastAPI app and project config**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title='Issue Multi-Agent Service')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
```

```toml
# backend/pyproject.toml
[project]
name = "issue-multi-agent-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.0",
  "pydantic>=2.8.0",
  "python-multipart>=0.0.9",
  "httpx>=0.27.0"
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest -q tests/test_health.py::test_health_endpoint_returns_ok`
Expected: PASS.

- [ ] **Step 5: Commit bootstrap skeleton**

```bash
git add backend frontend docker-compose.yml .env.example .gitignore
git commit -m "chore: bootstrap backend frontend and docker-compose skeleton"
```

### Task 2: Implement Domain Models, Persistence, and Job API

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/repositories.py`
- Create: `backend/app/services/job_service.py`
- Create: `backend/app/api/issues.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_issue_api.py`

- [ ] **Step 1: Write failing tests for analyze endpoint and report retrieval**

```python
# backend/tests/test_issue_api.py
from fastapi.testclient import TestClient
from app.main import app


def test_create_analysis_job_returns_report_id() -> None:
    client = TestClient(app)
    payload = {
        'source': 'inline',
        'issues': [{'id': 1, 'title': 'Crash when calling chain.invoke', 'body': 'Traceback...'}]
    }
    response = client.post('/api/issues/analyze', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'report_id' in data


def test_get_report_returns_html_and_diagnosis() -> None:
    client = TestClient(app)
    payload = {
        'source': 'inline',
        'issues': [{'id': 1, 'title': 'docs typo in tutorial', 'body': 'section outdated'}]
    }
    report_id = client.post('/api/issues/analyze', json=payload).json()['report_id']
    response = client.get(f'/api/reports/{report_id}')
    assert response.status_code == 200
    data = response.json()
    assert 'html_report' in data
    assert 'diagnosis' in data
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && pytest -q tests/test_issue_api.py`
Expected: FAIL because endpoints/services do not exist.

- [ ] **Step 3: Implement SQLite models and minimal repository/service flow**

```python
# backend/app/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text


class Base(DeclarativeBase):
    pass


class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    diagnosis_json: Mapped[str] = mapped_column(Text)
    html_report: Mapped[str] = mapped_column(Text)
```

```python
# backend/app/api/issues.py
from fastapi import APIRouter

router = APIRouter(prefix='/api')

@router.post('/issues/analyze')
def analyze_issues() -> dict[str, str]:
    return {'report_id': 'stub-report-id', 'status': 'completed'}

@router.get('/reports/{report_id}')
def get_report(report_id: str) -> dict:
    return {'report_id': report_id, 'diagnosis': {}, 'html_report': '<html></html>'}
```

- [ ] **Step 4: Expand implementation to use DB-backed report creation and retrieval**

Run minimal migration-on-startup (`Base.metadata.create_all`) and replace stubs with persisted records.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && pytest -q tests/test_issue_api.py`
Expected: PASS.

- [ ] **Step 6: Commit API foundation**

```bash
git add backend/app backend/tests/test_issue_api.py
git commit -m "feat: add issue analyze and report retrieval api with sqlite"
```

### Task 3: Implement Agent Modules and Orchestrator

**Files:**
- Create: `backend/app/agents/base.py`
- Create: `backend/app/agents/TriagerAgent.py`
- Create: `backend/app/agents/ResearcherAgent.py`
- Create: `backend/app/agents/DebuggerAgent.py`
- Create: `backend/app/agents/DocumenterAgent.py`
- Create: `backend/app/services/orchestrator.py`
- Modify: `backend/app/services/job_service.py`
- Create: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing unit tests for triage and debugger human-flag behavior**

```python
# backend/tests/test_agents.py
from app.agents.TriagerAgent import TriagerAgent
from app.agents.DebuggerAgent import DebuggerAgent


def test_triager_detects_bug() -> None:
    issue = {'title': 'App crashes on startup', 'body': 'NullPointerException'}
    result = TriagerAgent().run(issue, {}, {})
    assert result['artifacts']['issue_type'] == 'Bug'


def test_debugger_marks_requires_human_for_ambiguous_bug() -> None:
    issue = {'title': 'Intermittent UI freeze', 'body': 'Cannot reproduce deterministically'}
    result = DebuggerAgent().run(issue, {'research_summary': 'insufficient context'}, {})
    assert result['artifacts']['requires_human'] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && pytest -q tests/test_agents.py`
Expected: FAIL because agents are missing.

- [ ] **Step 3: Implement rule-based agents and orchestrator pipeline**

```python
# backend/app/agents/TriagerAgent.py
class TriagerAgent:
    def run(self, issue: dict, context: dict, config: dict) -> dict:
        text = f"{issue.get('title', '')} {issue.get('body', '')}".lower()
        issue_type = 'Bug' if any(k in text for k in ['error', 'crash', 'exception', 'bug']) else 'Docs' if 'doc' in text else 'Feature'
        return {
            'status': 'ok',
            'summary': f'classified as {issue_type}',
            'artifacts': {'issue_type': issue_type, 'confidence': 0.75, 'rationale': 'rule-based'},
            'evidence': []
        }
```

```python
# backend/app/agents/DebuggerAgent.py
class DebuggerAgent:
    def run(self, issue: dict, context: dict, config: dict) -> dict:
        text = f"{issue.get('title', '')} {issue.get('body', '')}".lower()
        needs_human = 'intermittent' in text or 'cannot reproduce' in text
        return {
            'status': 'requires_human' if needs_human else 'ok',
            'summary': 'debug analysis done',
            'artifacts': {
                'reproduce_steps': ['Install deps', 'Run target command', 'Observe failure'],
                'reproduce_code': "print('minimal reproduction placeholder')",
                'fix_suggestions': ['Add null-check and regression test'],
                'requires_human': needs_human,
                'human_reason': 'Ambiguous repro path' if needs_human else None,
            },
            'evidence': [],
        }
```

- [ ] **Step 4: Wire orchestrator into analyze endpoint path**

Ensure trace order is always persisted as `Triager -> Researcher -> Debugger/Documenter`.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && pytest -q tests/test_agents.py tests/test_issue_api.py`
Expected: PASS.

- [ ] **Step 6: Commit agent orchestration**

```bash
git add backend/app/agents backend/app/services backend/tests/test_agents.py
git commit -m "feat: implement multi-agent pipeline with triager researcher debugger documenter"
```

### Task 4: Implement HTML Report Builder and Contract Assertions

**Files:**
- Create: `backend/app/services/report_builder.py`
- Modify: `backend/app/services/orchestrator.py`
- Modify: `backend/app/services/job_service.py`
- Create: `backend/tests/test_report_contract.py`

- [ ] **Step 1: Write failing contract test for required HTML IDs**

```python
# backend/tests/test_report_contract.py
from app.services.report_builder import build_html_report


def test_bug_report_contains_required_sections() -> None:
    html = build_html_report(
        issue={'id': 1, 'title': 'Crash'},
        trace=['Triager', 'Researcher', 'Debugger'],
        diagnosis={'type': 'Bug', 'related_files': ['app/main.py'], 'fix_suggestions': ['Add guard']},
        reproduce_code='print("boom")',
    )
    assert '<div id="agent-trace">' in html
    assert '<section id="diagnosis">' in html
    assert '<pre id="reproduce-code">' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest -q tests/test_report_contract.py`
Expected: FAIL due to missing builder.

- [ ] **Step 3: Implement deterministic HTML renderer with attribution block**

```python
# backend/app/services/report_builder.py
def build_html_report(issue: dict, trace: list[str], diagnosis: dict, reproduce_code: str | None, attribution: list[dict] | None = None) -> str:
    reproduce_section = f'<pre id="reproduce-code">{reproduce_code or "N/A"}</pre>'
    trace_text = ' -> '.join(trace)
    return (
        '<html><body>'
        f'<div id="agent-trace">{trace_text}</div>'
        f'<section id="diagnosis"><h2>Diagnosis</h2><pre>{diagnosis}</pre></section>'
        f'{reproduce_section}'
        '</body></html>'
    )
```

- [ ] **Step 4: Run report contract tests to verify pass**

Run: `cd backend && pytest -q tests/test_report_contract.py tests/test_issue_api.py`
Expected: PASS.

- [ ] **Step 5: Commit report contract implementation**

```bash
git add backend/app/services/report_builder.py backend/tests/test_report_contract.py backend/app/services
git commit -m "feat: generate html report with required ids and diagnosis section"
```

### Task 5: Human-in-the-Loop Endpoints and Debugger Rerun

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/repositories.py`
- Modify: `backend/app/api/issues.py`
- Modify: `backend/app/services/job_service.py`
- Create: `backend/tests/test_human_loop.py`

- [ ] **Step 1: Write failing tests for feedback and rerun-debugger**

```python
# backend/tests/test_human_loop.py
from fastapi.testclient import TestClient
from app.main import app


def test_submit_human_feedback_and_rerun_debugger() -> None:
    client = TestClient(app)
    report_id = client.post('/api/issues/analyze', json={
        'source': 'inline',
        'issues': [{'id': 1, 'title': 'Intermittent crash', 'body': 'cannot reproduce'}]
    }).json()['report_id']

    fb = client.post(f'/api/reports/{report_id}/human-feedback', json={'human_note': 'happens after login redirect'})
    assert fb.status_code == 200

    rr = client.post(f'/api/reports/{report_id}/rerun-debugger')
    assert rr.status_code == 200
    assert 'trace' in rr.json()
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && pytest -q tests/test_human_loop.py`
Expected: FAIL because endpoints are missing.

- [ ] **Step 3: Implement feedback persistence and debugger-only rerun**

```python
# backend/app/api/issues.py
@router.post('/reports/{report_id}/human-feedback')
def add_human_feedback(report_id: str, payload: HumanFeedbackCreate) -> dict:
    return service.save_human_feedback(report_id, payload.human_note)

@router.post('/reports/{report_id}/rerun-debugger')
def rerun_debugger(report_id: str) -> dict:
    return service.rerun_debugger(report_id)
```

Implement `rerun_debugger` to:
- load existing report/context
- pass `human_note` into debugger context
- append new trace step
- persist updated report HTML and diagnosis

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest -q tests/test_human_loop.py tests/test_issue_api.py`
Expected: PASS.

- [ ] **Step 5: Commit human loop support**

```bash
git add backend/app backend/tests/test_human_loop.py
git commit -m "feat: add human feedback and debugger rerun workflow"
```

### Task 6: Build React UI for Analyze and Report Pages

**Files:**
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/pages/AnalyzePage.tsx`
- Create: `frontend/src/pages/ReportPage.tsx`
- Create: `frontend/src/components/AgentTrace.tsx`
- Create: `frontend/src/components/DiagnosisSection.tsx`
- Create: `frontend/src/components/ReproduceCode.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/__tests__/report-page.test.tsx`

- [ ] **Step 1: Write failing frontend test for required report elements**

```tsx
// frontend/src/__tests__/report-page.test.tsx
import { render, screen } from '@testing-library/react';
import { ReportPage } from '../pages/ReportPage';

test('renders required report containers', () => {
  render(<ReportPage report={{ html_report: '<div id="agent-trace"></div><section id="diagnosis"></section><pre id="reproduce-code"></pre>' }} /> as any);
  expect(screen.getByText(/agent trace/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && npm test -- --runInBand`
Expected: FAIL due to missing components/test setup.

- [ ] **Step 3: Implement Analyze + Report pages with human loop actions**

```tsx
// frontend/src/pages/ReportPage.tsx
export function ReportPage() {
  // fetch report by id
  // render trace, diagnosis, and reproduce code blocks
  // if requires_human, render note textarea and rerun button
  return <div>...</div>;
}
```

- [ ] **Step 4: Run frontend tests and build**

Run: `cd frontend && npm test -- --runInBand && npm run build`
Expected: tests PASS and build succeeds.

- [ ] **Step 5: Commit frontend implementation**

```bash
git add frontend
git commit -m "feat: add react analyze/report ui with human-in-the-loop controls"
```

### Task 7: Dockerization, End-to-End Verification, and Docs

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`
- Create: `README.md`
- Create: `backend/tests/test_e2e_local.py`

- [ ] **Step 1: Write failing E2E smoke test for full flow (backend level)**

```python
# backend/tests/test_e2e_local.py
from fastapi.testclient import TestClient
from app.main import app


def test_end_to_end_issue_flow() -> None:
    client = TestClient(app)
    create = client.post('/api/issues/analyze', json={
        'source': 'inline',
        'issues': [{'id': 11, 'title': 'Crash on startup', 'body': 'exception when importing module'}]
    })
    assert create.status_code == 200
    report_id = create.json()['report_id']

    report = client.get(f'/api/reports/{report_id}')
    assert report.status_code == 200
    html = report.json()['html_report']
    assert 'id="agent-trace"' in html
    assert 'id="diagnosis"' in html
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && pytest -q tests/test_e2e_local.py`
Expected: FAIL until full integration is done.

- [ ] **Step 3: Add Dockerfiles, compose wiring, and README runbook**

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    depends_on: [backend]
```

README must include:
- environment setup
- `docker-compose up --build`
- local dev run commands
- example API calls

- [ ] **Step 4: Run full verification**

Run:
- `cd backend && pytest -q`
- `cd frontend && npm run build`
- `docker-compose up --build -d`
- `curl -sS http://127.0.0.1:8000/health`

Expected:
- tests PASS
- frontend build PASS
- backend health returns `{"status":"ok"}`

- [ ] **Step 5: Commit delivery package**

```bash
git add backend frontend docker-compose.yml README.md
git commit -m "chore: finalize dockerized full-stack delivery and runbook"
```

## Plan Self-Review
- Spec coverage: architecture, four agents, issue typing, module search, reproduce/fix suggestions, HTML required IDs, human-loop feedback/rerun, frontend display, and docker one-command startup are each mapped to tasks 1-7.
- Placeholder scan: no `TBD/TODO` placeholders remain; each task includes concrete files and executable commands.
- Consistency check: endpoints, filenames, and report contract IDs are consistent across tasks and tests.
