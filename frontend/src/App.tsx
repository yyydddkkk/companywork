import { useState } from 'react';
import SegmentedControl from './components/SegmentedControl';
import AnalyzePage from './pages/AnalyzePage';
import ReportPage from './pages/ReportPage';

type View = 'analyze' | 'report';

export default function App() {
  const [view, setView] = useState<View>('analyze');
  const [reportIdInput, setReportIdInput] = useState('');
  const [activeReportId, setActiveReportId] = useState('');

  function openReport(reportId: string) {
    setActiveReportId(reportId);
    setReportIdInput(reportId);
    setView('report');
  }

  return (
    <div className="app-shell">
      <div className="noise" aria-hidden="true" />
      <header className="topbar glass">
        <div>
          <p className="eyebrow">多智能体 Issue 流程</p>
          <h1>Issue 智能诊断控制台</h1>
        </div>
        <SegmentedControl
          options={[
            { label: '分析', value: 'analyze' },
            { label: '报告', value: 'report' },
          ]}
          value={view}
          onChange={(next) => setView(next)}
        />
      </header>

      <main className="content-wrap">
        {view === 'analyze' ? (
          <AnalyzePage onCompleted={openReport} />
        ) : (
          <>
            <section className="card report-picker">
              <h2>打开报告</h2>
              <div className="row-two">
                <label>
                  报告 ID
                  <input
                    value={reportIdInput}
                    onChange={(e) => setReportIdInput(e.target.value)}
                    placeholder="输入 report_id"
                  />
                </label>
                <button
                  className="primary-btn"
                  type="button"
                  disabled={!reportIdInput.trim()}
                  onClick={() => setActiveReportId(reportIdInput.trim())}
                >
                  加载报告
                </button>
              </div>
            </section>
            {activeReportId ? <ReportPage reportId={activeReportId} /> : null}
          </>
        )}
      </main>
    </div>
  );
}
