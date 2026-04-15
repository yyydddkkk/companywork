import type { AnalyzeResponse, JobStatusResponse, ReportResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function analyzeInline(issue: {
  title: string;
  body: string;
  external_id?: string;
  url?: string;
}): Promise<AnalyzeResponse> {
  const payload = {
    source: 'inline',
    issues: [issue],
  };
  const res = await fetch(`${API_BASE}/api/issues/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse<AnalyzeResponse>(res);
}

export async function analyzeGitHub(input: {
  owner: string;
  repo: string;
  issue_number: number;
}): Promise<AnalyzeResponse> {
  const payload = {
    source: 'github',
    issues: [],
    github: input,
  };
  const res = await fetch(`${API_BASE}/api/issues/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse<AnalyzeResponse>(res);
}

export async function analyzeUpload(file: File): Promise<AnalyzeResponse> {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API_BASE}/api/issues/analyze/upload`, {
    method: 'POST',
    body: fd,
  });
  return parseResponse<AnalyzeResponse>(res);
}

export async function fetchReport(reportId: string): Promise<ReportResponse> {
  const res = await fetch(`${API_BASE}/api/reports/${encodeURIComponent(reportId)}`);
  return parseResponse<ReportResponse>(res);
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`);
  return parseResponse<JobStatusResponse>(res);
}

export async function submitHumanFeedback(reportId: string, note: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/reports/${encodeURIComponent(reportId)}/human-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_note: note }),
  });
  await parseResponse(res);
}

export async function rerunDebugger(reportId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/reports/${encodeURIComponent(reportId)}/rerun-debugger`, {
    method: 'POST',
  });
  await parseResponse(res);
}
