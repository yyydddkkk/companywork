from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .schemas import AnalyzeRequest, HumanFeedbackRequest
from .services.job_service import JobService


def create_app(overrides: dict[str, Any] | None = None) -> FastAPI:
    settings = load_settings(overrides)
    app = FastAPI(title='Issue Multi-Agent MVP')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    service = JobService(settings)
    app.state.settings = settings
    app.state.job_service = service

    @app.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok'}

    @app.post('/api/issues/analyze')
    def analyze(payload: AnalyzeRequest, request: Request) -> dict[str, Any]:
        return request.app.state.job_service.analyze(payload)

    @app.post('/api/issues/analyze/upload')
    async def analyze_upload(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        return request.app.state.job_service.analyze_upload(file.filename or 'issues.json', content)

    @app.get('/api/reports/{report_id}')
    def get_report(report_id: str, request: Request) -> dict[str, Any]:
        return request.app.state.job_service.get_report(report_id)

    @app.post('/api/reports/{report_id}/human-feedback')
    def add_human_feedback(report_id: str, payload: HumanFeedbackRequest, request: Request) -> dict[str, Any]:
        return request.app.state.job_service.add_human_feedback(report_id, payload.human_note)

    @app.post('/api/reports/{report_id}/rerun-debugger')
    def rerun_debugger(report_id: str, request: Request) -> dict[str, Any]:
        return request.app.state.job_service.rerun_debugger(report_id)

    return app


app = create_app()
