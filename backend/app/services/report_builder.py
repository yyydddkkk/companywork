from __future__ import annotations

from html import escape
from typing import Any


class ReportBuilder:
    def build(
        self,
        issue: dict[str, Any],
        trace: list[dict[str, Any]],
        diagnosis: dict[str, Any],
        requires_human: bool,
        feedback_entries: list[dict[str, Any]],
    ) -> str:
        trace_html = ''.join(
            '<article class="trace-step">'
            f"<h4>{escape(step['agent_name'])}</h4>"
            f"<p>Status: {escape(step['status'])}</p>"
            f"<p>{escape(step['summary'])}</p>"
            '</article>'
            for step in trace
        )
        related_files = ''.join(f'<li>{escape(path)}</li>' for path in diagnosis.get('related_files', [])) or '<li>No related files found</li>'
        fix_suggestions = ''.join(f'<li>{escape(item)}</li>' for item in diagnosis.get('fix_suggestions', [])) or '<li>No fix suggestion available</li>'
        feedback_html = ''.join(
            f"<li>{escape(entry['human_note'])}</li>"
            for entry in feedback_entries
        )
        reproduce_block = ''
        if diagnosis.get('type') == 'Bug':
            reproduce_block = (
                '<section>'
                '<h3>Reproduction</h3>'
                f"<pre id=\"reproduce-code\">{escape(diagnosis.get('reproduce_code', '') or 'No deterministic reproduction code yet.')}</pre>"
                '</section>'
            )

        return f"""
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <title>Issue Report {escape(issue.get('title', ''))}</title>
  </head>
  <body>
    <main>
      <h1>{escape(issue.get('title', 'Untitled Issue'))}</h1>
      <p>{escape(issue.get('body', ''))}</p>
      <div id=\"agent-trace\">{trace_html}</div>
      <section id=\"diagnosis\">
        <h2>Diagnosis</h2>
        <p><strong>type:</strong> {escape(diagnosis.get('type', 'Unknown'))}</p>
        <p><strong>root_cause_hypothesis:</strong> {escape(diagnosis.get('root_cause_hypothesis', 'Not available'))}</p>
        <p><strong>requires_human:</strong> {str(requires_human).lower()}</p>
        <h3>Related Files</h3>
        <ul>{related_files}</ul>
        <h3>Fix Suggestions</h3>
        <ul>{fix_suggestions}</ul>
      </section>
      {reproduce_block}
      <section>
        <h3>Human Feedback</h3>
        <ul>{feedback_html or '<li>No human feedback submitted</li>'}</ul>
      </section>
    </main>
  </body>
</html>
""".strip()
