"""Deploy research report as static HTML to the reports directory."""
from pathlib import Path
from datetime import datetime

from models import ResearchReport
from config import config
from report_store import persist_report


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Search Agent</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #09090b;
    color: #f4f4f5;
    line-height: 1.7;
  }}
  .container {{ max-width: 800px; margin: 0 auto; padding: 3rem 1.5rem; }}
  h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 0.75rem; }}
  h2 {{ font-size: 1.4rem; font-weight: 600; margin-top: 2.5rem; margin-bottom: 0.75rem; }}
  h3 {{ font-size: 1.1rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem; }}
  p {{ margin: 0.75rem 0; }}
  .meta {{ color: #71717a; font-size: 0.875rem; margin-bottom: 2rem; }}
  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  sup a {{ font-weight: 600; }}
  hr {{ border: none; border-top: 1px solid #27272a; margin: 2rem 0; }}
  ul {{ padding-left: 1.5rem; }}
  li {{ margin: 0.3rem 0; }}
  blockquote {{
    border-left: 3px solid #3f3f46;
    padding-left: 1rem;
    color: #a1a1aa;
    font-style: italic;
    margin: 1rem 0;
  }}
  strong {{ color: #e4e4e7; }}
  .sources {{ margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #27272a; }}
  .sources ol {{ padding-left: 1.2rem; font-size: 0.875rem; color: #a1a1aa; }}
  .sources li {{ margin: 0.5rem 0; }}
  .back-link {{ display: inline-block; margin-bottom: 2rem; font-size: 0.875rem; color: #71717a; }}
  .trust-signals {{
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 0.5rem;
    padding: 1rem 1.25rem;
    margin-bottom: 2rem;
    font-size: 0.875rem;
    color: #a1a1aa;
  }}
</style>
</head>
<body>
<div class="container">
  <a href="/" class="back-link">← Search Agent</a>
  <h1>{title}</h1>
  <div class="trust-signals">
    ⏱ {execution_time}s · 🔗 {source_count} sources · 📅 {date}
  </div>
  {body}
  <div class="sources">
    <h2>📚 Sources</h2>
    <ol>
      {sources}
    </ol>
  </div>
</div>
</body>
</html>"""


def _markdown_to_html(md: str) -> str:
    """Convert report markdown to HTML."""
    import re

    html = md

    # Citation markers: [^1] → clickable superscript
    html = re.sub(
        r"\[\^(\d+)\](?!:)",
        r'<sup><a href="#source-\1" id="cite-\1">[\1]</a></sup>',
        html,
    )

    # Source footnotes: [^1]: text → anchor + remove
    html = re.sub(
        r"\[\^(\d+)\]: (.+)",
        r'',
        html,
    )

    # Headers
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Inline links
    html = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        html,
    )

    # Horizontal rules
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

    # List items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Paragraphs: double newline
    html = re.sub(r"\n\n", r"</p><p>", html)
    html = re.sub(r"\n", r"<br>", html)
    html = f"<p>{html}</p>"

    return html


def _build_sources_html(citations: list) -> str:
    """Build the sources list HTML from citations."""
    items = []
    for c in citations:
        items.append(
            f'<li id="source-{c.index}">'
            f'<strong>[{c.index}]</strong> '
            f'<a href="{c.source_url}" target="_blank" rel="noopener">{c.source_name}</a>'
            f' — &ldquo;{c.quoted_text[:200]}{"..." if len(c.quoted_text) > 200 else ""}&rdquo;'
            f' <a href="#cite-{c.index}" style="font-size:0.75rem;color:#71717a;">↑ back</a>'
            f'</li>'
        )
    return "\n".join(items)


async def deploy_report(report: ResearchReport) -> str:
    """Generate a static HTML file for the report and return its relative URL."""
    output_dir = Path(config.report_output_dir)
    report_dir = output_dir / report.slug
    report_dir.mkdir(parents=True, exist_ok=True)

    body_html = _markdown_to_html(report.markdown)
    sources_html = _build_sources_html(report.citations)

    metadata = report.metadata
    exec_time = f"{metadata.execution_time_seconds:.1f}" if metadata else "?"
    source_count = metadata.source_count if metadata else len(report.citations)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    html = HTML_TEMPLATE.format(
        title=report.topic,
        execution_time=exec_time,
        source_count=source_count,
        date=date_str,
        body=body_html,
        sources=sources_html,
    )

    index_path = report_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    html_url = f"/research/{report.slug}/"
    report.html_url = html_url
    persist_report(report)

    return html_url
