import { useEffect, useMemo, useState } from 'react';
import { fetchJobStatus, fetchReport, rerunDebugger, submitHumanFeedback } from '../lib/api';
import type { JobStatusResponse, ReportResponse } from '../lib/types';

interface ReportPageProps {
  reportId: string;
}

export default function ReportPage({ reportId }: ReportPageProps) {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const canRerun = useMemo(
    () => report?.requires_human && feedback.trim().length >= 3,
    [report?.requires_human, feedback],
  );

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const directReport = await fetchReport(reportId);
      setReport(directReport);
      setJob(null);
    } catch (err) {
      const text = err instanceof Error ? err.message : '加载报告失败';
      if (!text.includes('404')) {
        setError(text);
        return;
      }
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  useEffect(() => {
    if (report || error) return;
    let disposed = false;
    const timer = window.setInterval(async () => {
      try {
        const status = await fetchJobStatus(reportId);
        if (disposed) return;
        setJob(status);
        if (status.report_ready && status.report_id) {
          const completed = await fetchReport(status.report_id);
          if (disposed) return;
          setReport(completed);
          setLoading(false);
          window.clearInterval(timer);
        } else if (status.status === 'failed') {
          setError('分析任务失败，请查看后端日志。');
          setLoading(false);
          window.clearInterval(timer);
        } else {
          setLoading(true);
        }
      } catch {
        setError('无法获取任务状态，请确认后端服务是否正常。');
        setLoading(false);
        window.clearInterval(timer);
      }
    }, 1200);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [report, error, reportId]);

  async function handleSubmitFeedbackAndRerun() {
    if (!report) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitHumanFeedback(report.report_id, feedback.trim());
      await rerunDebugger(report.report_id);
      await load();
      setFeedback('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <section className="card">
        <h3>分析进行中</h3>
        <p className="muted">
          当前状态：{formatStatus(job?.status ?? 'queued')}
        </p>
        <div id="agent-trace" className="trace-grid" style={{ marginTop: 10 }}>
          {(job?.agent_trace ?? []).map((step) => (
            <div key={step.id} className="trace-node">
              <p className="trace-title">
                {step.step_index}. {step.agent_name}
                <span className={getLLMBadgeClass(step.artifacts)}> {getLLMBadgeText(step.artifacts)}</span>
              </p>
              <p className="trace-status">{step.status}</p>
              <p className="trace-summary">{step.summary}</p>
            </div>
          ))}
          {(job?.agent_trace ?? []).length === 0 ? <p className="muted">等待 Triager 启动...</p> : null}
        </div>
      </section>
    );
  }

  if (error || !report) {
    return (
      <section className="card">
        <p className="error-text">{error ?? '未找到报告'}</p>
      </section>
    );
  }

  return (
    <section className="report-layout">
      <article className="card glass">
        <header className="card-header">
          <h2>{report.issue.title}</h2>
          <p>类型：{report.diagnosis.type}</p>
        </header>

        <section id="diagnosis" className="diagnosis-block">
          <h3>诊断结果</h3>
          <p><strong>置信度：</strong> {(report.diagnosis.triage_confidence * 100).toFixed(1)}%</p>
          <p><strong>判定依据：</strong> {report.diagnosis.triage_rationale}</p>
          <p><strong>检索来源：</strong> {formatSourceScope(report.diagnosis.source_scope)}</p>
          <p><strong>目标仓库：</strong> {report.diagnosis.source_repo || '本地项目'}</p>
          {report.diagnosis.degraded_reason ? (
            <p className="error-text"><strong>降级原因：</strong> {report.diagnosis.degraded_reason}</p>
          ) : null}
          {report.diagnosis.llm_error_message ? (
            <p className="error-text"><strong>模型错误：</strong> {report.diagnosis.llm_error_message}</p>
          ) : null}
          <p><strong>根因假设：</strong> {report.diagnosis.root_cause_hypothesis}</p>
          <h4>相关文件</h4>
          <ul>
            {report.diagnosis.related_files.length > 0 ? report.diagnosis.related_files.map((item) => <li key={item}>{item}</li>) : <li>暂无</li>}
          </ul>
          <h4>修复建议</h4>
          <ul>
            {report.diagnosis.fix_suggestions.length > 0 ? report.diagnosis.fix_suggestions.map((item) => <li key={item}>{item}</li>) : <li>暂无</li>}
          </ul>
        </section>

        {report.diagnosis.type === 'Bug' ? (
          <section>
            <h3>最小复现</h3>
            <pre id="reproduce-code">{report.diagnosis.reproduce_code || '# 暂无确定性的复现代码'}</pre>
          </section>
        ) : null}
      </article>

      <article className="card glass">
        <h3>Agent 执行路径</h3>
        <div id="agent-trace" className="trace-grid">
          {report.agent_trace.map((step) => (
            <div key={step.id} className="trace-node">
              <p className="trace-title">
                {step.step_index}. {step.agent_name}
                <span className={getLLMBadgeClass(step.artifacts)}> {getLLMBadgeText(step.artifacts)}</span>
              </p>
              <p className="trace-status">{step.status}</p>
              <p className="trace-summary">{step.summary}</p>
            </div>
          ))}
        </div>
      </article>

      <article className="card">
        <h3>HTML 报告预览</h3>
        <iframe title="html-report" className="report-frame" srcDoc={report.html_report} />
      </article>

      {report.requires_human ? (
        <article className="card human-loop">
          <h3>人工介入</h3>
          <p className="muted">
            {report.diagnosis.human_reason || 'Debugger 标记了 requires_human=true，请补充上下文后重新执行。'}
          </p>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={4}
            placeholder="例如：仅在 Python 3.11 + uvicorn --reload 场景可复现"
          />
          <button
            type="button"
            className="primary-btn"
            disabled={!canRerun || submitting}
            onClick={handleSubmitFeedbackAndRerun}
          >
            {submitting ? '提交中...' : '提交反馈并重跑 Debugger'}
          </button>
        </article>
      ) : null}
    </section>
  );
}

function formatStatus(status: string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    triager_running: 'Triager 分析中',
    researcher_running: 'Researcher 检索中',
    debugger_running: 'Debugger 诊断中',
    documenter_running: 'Documenter 文档分析中',
    completed: '已完成',
    failed: '失败',
  };
  return map[status] ?? status;
}

function formatSourceScope(scope: string): string {
  const map: Record<string, string> = {
    github_repo: 'GitHub 仓库代码',
    local_project: '本地项目代码',
    issue_only_fallback: '仅基于 Issue 文本(降级)',
  };
  return map[scope] ?? scope;
}

function getLLMBadgeText(artifacts: Record<string, unknown>): string {
  if (typeof artifacts.llm_error_kind === 'string' && artifacts.llm_error_kind) return '模型失败-需人工';
  if (artifacts.llm_used === true) return '模型';
  if (artifacts.llm_enabled === true) return '规则(模型未命中)';
  return '规则';
}

function getLLMBadgeClass(artifacts: Record<string, unknown>): string {
  if (typeof artifacts.llm_error_kind === 'string' && artifacts.llm_error_kind) return 'trace-badge trace-badge-rule';
  if (artifacts.llm_used === true) return 'trace-badge trace-badge-llm';
  return 'trace-badge trace-badge-rule';
}
