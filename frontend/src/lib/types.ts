export type IssueType = 'Bug' | 'Feature' | 'Docs' | 'Question';

export interface AnalyzeResponse {
  report_id: string;
  job_id: string;
  status: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  report_ready: boolean;
  report_id?: string | null;
  agent_trace: AgentTraceItem[];
}

export interface AgentTraceItem {
  id: string;
  agent_name: string;
  step_index: number;
  status: string;
  summary: string;
  artifacts: Record<string, unknown>;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface Diagnosis {
  type: IssueType;
  issue_title: string;
  triage_confidence: number;
  triage_rationale: string;
  source_scope: 'github_repo' | 'local_project' | 'issue_only_fallback' | string;
  source_repo?: string;
  degraded_reason?: string;
  related_files: string[];
  research_summary: string;
  root_cause_hypothesis: string;
  fix_suggestions: string[];
  reproduce_steps: string[];
  reproduce_code: string;
  doc_targets: string[];
  gap_analysis: string;
  suggested_updates: string[];
  requires_human: boolean;
  human_reason?: string;
  llm_error_kind?: string;
  llm_error_message?: string;
}

export interface ReportResponse {
  report_id: string;
  job_id: string;
  issue: {
    id: string;
    external_id?: string;
    title: string;
    body: string;
    url?: string;
  };
  diagnosis: Diagnosis;
  requires_human: boolean;
  rerun_count: number;
  agent_trace: AgentTraceItem[];
  html_report: string;
  human_feedback: Array<{
    id: string;
    human_note: string;
    created_at: string;
  }>;
}
