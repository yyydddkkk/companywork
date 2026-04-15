import { FormEvent, useMemo, useState } from 'react';
import { analyzeGitHub, analyzeInline, analyzeUpload } from '../lib/api';

type AnalyzeMode = 'inline' | 'github' | 'upload';

interface AnalyzePageProps {
  onCompleted: (reportId: string) => void;
}

export default function AnalyzePage({ onCompleted }: AnalyzePageProps) {
  const [mode, setMode] = useState<AnalyzeMode>('inline');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [githubIssueUrl, setGithubIssueUrl] = useState('');

  const [title, setTitle] = useState('FastAPI 在环境变量包含空格时启动失败');
  const [body, setBody] = useState('修改 `.env` 后应用启动崩溃，堆栈指向配置解析模块。');
  const [externalId, setExternalId] = useState('ISSUE-001');
  const [url, setUrl] = useState('https://github.com/tiangolo/fastapi/issues/0000');

  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const helperText = useMemo(() => {
    if (mode === 'inline') return '直接输入 Issue 内容，适合快速验证流程。';
    if (mode === 'github') return '可直接粘贴 GitHub Issue 链接，或手动输入 owner/repo/issue_number。';
    return '上传 JSON 或 CSV 的 issue 列表，系统会自动读取第一条作为主分析目标。';
  }, [mode]);

  function parseGitHubIssueUrl(raw: string): { owner: string; repo: string; issueNumber: number } | null {
    const value = raw.trim();
    if (!value) return null;
    const match = value.match(/^https?:\/\/github\.com\/([^/\s]+)\/([^/\s]+)\/issues\/(\d+)(?:[/?#].*)?$/i);
    if (!match) return null;
    return {
      owner: match[1],
      repo: match[2],
      issueNumber: Number(match[3]),
    };
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      let reportId = '';
      const parsedUrl = parseGitHubIssueUrl(githubIssueUrl);
      if (parsedUrl) {
        const res = await analyzeGitHub({
          owner: parsedUrl.owner,
          repo: parsedUrl.repo,
          issue_number: parsedUrl.issueNumber,
        });
        reportId = res.report_id;
      } else if (githubIssueUrl.trim()) {
        throw new Error('GitHub 链接格式不正确，请使用 https://github.com/<owner>/<repo>/issues/<number>');
      } else if (mode === 'inline') {
        const res = await analyzeInline({ title, body, external_id: externalId, url });
        reportId = res.report_id;
      } else if (mode === 'github') {
        throw new Error('请先填写有效的 GitHub Issue 链接');
      } else {
        if (!uploadFile) throw new Error('请先选择上传文件');
        const res = await analyzeUpload(uploadFile);
        reportId = res.report_id;
      }
      onCompleted(reportId);
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card glass">
      <header className="card-header">
        <h2>Issue 分析器</h2>
        <p>{helperText}</p>
      </header>

      <div className="mode-tabs" role="tablist" aria-label="分析模式">
        <button className={mode === 'inline' ? 'chip active' : 'chip'} type="button" onClick={() => setMode('inline')}>
          直接输入
        </button>
        <button className={mode === 'github' ? 'chip active' : 'chip'} type="button" onClick={() => setMode('github')}>
          GitHub
        </button>
        <button className={mode === 'upload' ? 'chip active' : 'chip'} type="button" onClick={() => setMode('upload')}>
          文件上传
        </button>
      </div>

      <form onSubmit={handleSubmit} className="form-grid">
        {mode === 'github' && (
          <label>
            GitHub Issue 链接
            <input
              value={githubIssueUrl}
              onChange={(e) => setGithubIssueUrl(e.target.value)}
              placeholder="https://github.com/langchain-ai/langchain/issues/12345"
              required
            />
          </label>
        )}

        {mode === 'inline' && (
          <>
            <label>
              标题
              <input value={title} onChange={(e) => setTitle(e.target.value)} required />
            </label>
            <label>
              描述
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} required />
            </label>
            <div className="row-two">
              <label>
                外部 ID
                <input value={externalId} onChange={(e) => setExternalId(e.target.value)} />
              </label>
              <label>
                URL
                <input value={url} onChange={(e) => setUrl(e.target.value)} />
              </label>
            </div>
          </>
        )}

        {mode === 'upload' && (
          <label>
            上传文件
            <input
              type="file"
              accept=".json,.csv"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
        )}

        {error ? <p className="error-text">{error}</p> : null}

        <button className="primary-btn" disabled={loading} type="submit">
          {loading ? '分析中...' : '开始分析'}
        </button>
      </form>
    </section>
  );
}
