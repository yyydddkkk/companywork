# GitHub Issue Multi-Agent Diagnostic System Design

## 1. Background and Goal
Build a runnable full-stack MVP that ingests GitHub Issues (or uploaded issue lists), runs a coordinated multi-agent pipeline, and produces attribution-aware HTML diagnosis reports.

Primary goals:
- Classify issue type: `Bug | Feature | Docs | Question`
- Locate likely relevant code/document modules
- Generate minimal reproduction steps or repair suggestions
- Support human-in-the-loop when debugging confidence is insufficient
- Render report in a Vite + React frontend
- One-command startup with Docker Compose

Out of scope for MVP:
- Enterprise workflow (approval chains, assignee orchestration)
- Distributed agent microservices
- Highly customized per-repo static analysis parsers

## 2. Architecture

### 2.1 High-Level Components
- `backend/` (`Python + FastAPI`):
  - Issue ingestion adapters (GitHub API, JSON/CSV upload)
  - Agent orchestrator
  - Agent implementations:
    - `TriagerAgent.py`
    - `ResearcherAgent.py`
    - `DebuggerAgent.py`
    - `DocumenterAgent.py`
  - Report builder (HTML + structured JSON)
  - Persistence (SQLite)
- `frontend/` (`Vite + React`):
  - Task creation UI
  - Report view UI
  - Human feedback UI and rerun trigger
- `docker-compose.yml`:
  - `backend` service
  - `frontend` service

### 2.2 Orchestration Flow
Canonical execution path:
1. `Triager` classifies issue type and confidence
2. `Researcher` searches `codebase/` and `docs/` context
3. Branch execution:
   - `Bug` -> `Debugger`
   - `Docs` -> `Documenter`
   - `Feature/Question` -> recommendation synthesis in orchestrator
4. `ReportBuilder` aggregates artifacts and emits final HTML report

Trace is always captured as ordered steps for visualization.

## 3. Agent Contracts

## 3.1 Shared Input Model
Each agent receives:
- `issue`: normalized issue payload
- `context`: accumulated artifacts from previous agents
- `config`: runtime settings (LLM enabled, model name, thresholds)

Each agent returns:
- `status`: `ok | requires_human | failed`
- `summary`: concise natural-language output
- `artifacts`: structured data specific to agent
- `evidence`: list of supporting snippets/paths

### 3.2 TriagerAgent.py
Responsibilities:
- Classify type: `Bug | Feature | Docs | Question`
- Return confidence and rationale

Strategy:
- Rule-based classifier first (keyword + phrase patterns)
- Optional LLM refinement if API key exists

Output fields:
- `issue_type`
- `confidence`
- `rationale`

### 3.3 ResearcherAgent.py
Responsibilities:
- Cross-search repository `codebase/` and `docs/`
- Identify likely related files/sections

Strategy:
- Query expansion from issue text
- Fast text search + top-k snippets
- Optional LLM ranking for relevance ordering

Output fields:
- `related_files[]`
- `code_snippets[]`
- `doc_snippets[]`
- `research_summary`

### 3.4 DebuggerAgent.py
Responsibilities:
- For Bug issues, produce:
  - minimal reproduction steps/code, or
  - concrete fix recommendations
- Mark complexity requiring human intervention

`requires_human=true` when:
- Multi-step UI/integration interactions cannot be deterministically inferred
- Contradictory signals or insufficient evidence
- Potentially high-risk fix requiring domain judgment

Output fields:
- `reproduce_steps[]`
- `reproduce_code`
- `fix_suggestions[]`
- `requires_human`
- `human_reason`

### 3.5 DocumenterAgent.py
Responsibilities:
- For Docs issues, locate missing/outdated docs
- Propose update targets and draft changes

Output fields:
- `doc_targets[]`
- `gap_analysis`
- `suggested_updates[]`

## 4. Human-in-the-Loop Design
Chosen mode: **B** (mark + human note + rerun).

Flow:
1. Debugger marks `requires_human=true`
2. Frontend report page shows "Human action required" card
3. Human submits `human_note`
4. Backend stores note and reruns **Debugger only** for same analysis job
5. New debugger output appended to trace/history

Data persisted:
- `human_note`
- `submitted_at`
- `rerun_attempt`
- `debugger_result_before`
- `debugger_result_after`

## 5. Report Requirements (HTML)
Generated report must include:
- `<div id="agent-trace">`:
  - Ordered path view, e.g. `Triager -> Researcher -> Debugger`
  - Include per-step status and timing
- `<section id="diagnosis">`:
  - Structured fields:
    - `type`
    - `related_files`
    - `root_cause_hypothesis`
    - `fix_suggestions`
- `<pre id="reproduce-code">`:
  - Mandatory for Bug reports
  - Omitted (or empty with explanatory text) for non-Bug

Attribution section must map each conclusion to evidence source:
- issue excerpt
- code snippet + file path
- docs snippet + path

## 6. Backend API (MVP)
- `POST /api/issues/analyze`
  - Input: source info (`github` with repo/issue ids, or inline list)
  - Output: `report_id`, initial status
- `POST /api/issues/analyze/upload`
  - Input: JSON/CSV file
  - Output: `report_id`
- `GET /api/reports/{report_id}`
  - Output: structured report JSON + rendered HTML
- `POST /api/reports/{report_id}/human-feedback`
  - Input: `human_note`
  - Output: persisted feedback record
- `POST /api/reports/{report_id}/rerun-debugger`
  - Output: updated debugger result and trace

## 7. Frontend UX (MVP)
Pages:
- `AnalyzePage`
  - Choose source: GitHub or upload
  - Submit job and navigate to report
- `ReportPage`
  - Render HTML report preview
  - Dedicated panels for trace and diagnosis
  - Human-in-the-loop card when required

Key UI blocks:
- Trace timeline component from ordered agent events
- Diagnosis summary panel
- Reproduction code viewer (`<pre>` render)
- Human note textarea + rerun button

## 8. Storage Model (SQLite)
Core tables:
- `analysis_jobs`
  - job metadata and source
- `issues`
  - normalized issue payload
- `agent_runs`
  - one record per agent execution
- `reports`
  - structured JSON + HTML artifact
- `human_feedback`
  - notes and rerun linkage

## 9. Intelligence Mode
Default mode: **Rules-first + optional LLM**.

- Without API key:
  - full pipeline still runs deterministically
- With API key:
  - LLM enhances classification quality, snippet ranking, and suggestion language

Provider abstraction:
- Single interface with pluggable OpenAI-compatible backend
- Env-based toggles for key/model/base URL

## 10. Error Handling and Reliability
- Input validation for malformed repos/issues/uploads
- Agent-level failures captured as step status, not whole-system crash
- Report still generated with partial diagnostics when possible
- Timeout/exception converted into actionable messages

## 11. Testing Strategy
- Unit tests:
  - Triager rule classification matrix
  - Researcher search ranking behavior
  - Debugger `requires_human` triggers
  - Documenter target detection
- Integration tests:
  - End-to-end analysis job lifecycle
  - Human feedback + rerun-debugger path
- Contract tests:
  - HTML report must contain required IDs

## 12. Deployment
`docker-compose up --build` should start:
- Backend on `:8000`
- Frontend on `:5173` (or mapped compose port)

Environment variables:
- GitHub token (optional but recommended for rate limits)
- LLM API key/base URL/model (optional)

## 13. Acceptance Criteria
- User can submit GitHub issue targets or upload issue list
- System executes agent path and stores trace
- Report HTML contains required sections/IDs
- Bug issues include minimal reproducible code block
- Complex debugging can trigger `requires_human=true`
- Human note can be submitted and debugger rerun succeeds
- Frontend visibly reflects updated trace and diagnosis
- Full stack starts with single Docker Compose command
