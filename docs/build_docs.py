"""Build docs/Documentation.pdf from docs/Documentation.md.

Markdown -> HTML (python-markdown) with print CSS -> PDF via a headless
Chromium browser (Edge or Chrome, whichever is installed).  Appendix
placeholders are filled from the real generated artefacts so the PDF can never
drift from the outputs.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BUILD = DOCS / "build"

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "msedge",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm;
        @bottom-center { content: "TDMA Schedule Planner & Optimizer  \\00b7  " counter(page) " / " counter(pages);
                         font: 8pt 'Segoe UI', sans-serif; color: #898781; } }
html { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 10pt; color: #0b0b0b;
       line-height: 1.45; background: #ffffff; }
body { margin: 0; }
h1 { font-size: 24pt; margin: 0 0 6pt; font-weight: 600; }
h2 { font-size: 15pt; margin: 18pt 0 6pt; font-weight: 600; border-bottom: 1px solid #e1e0d9; padding-bottom: 3pt; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; font-weight: 600; }
p, li { text-align: left; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.6pt; page-break-inside: avoid; }
th, td { border: 1px solid #e1e0d9; padding: 3pt 5pt; vertical-align: top; }
th { background: #f4f3ef; font-weight: 600; }
code { font-family: Consolas, 'Cascadia Mono', monospace; font-size: 8.6pt; background: #f4f3ef; padding: 0 2px; }
pre { background: #f7f7f5; border: 1px solid #e1e0d9; padding: 6pt; font-size: 7.4pt; line-height: 1.25;
      white-space: pre; overflow: hidden; page-break-inside: auto; }
pre code { background: none; padding: 0; font-size: 7.4pt; }
img { max-width: 100%; display: block; margin: 6pt auto 10pt; page-break-inside: avoid; }
.pagebreak { page-break-after: always; }
.cover { padding-top: 40mm; }
.cover h1 { font-size: 30pt; }
.cover h2 { border: none; font-weight: 400; color: #52514e; font-size: 15pt; margin-top: 4pt; }
.cover table { margin-top: 18mm; font-size: 9.5pt; }
blockquote { border-left: 3px solid #2a78d6; margin: 6pt 0; padding: 2pt 8pt; color: #52514e; }
"""


def fill_placeholders(text: str) -> str:
    def code(path: Path) -> str:
        return path.read_text(encoding="utf-8").rstrip("\n")
    repl = {
        "{{GRID_REPORT}}": code(ROOT / "outputs" / "grid_4x4_report.txt"),
        "{{GRID_SCHEDULE_XML}}": code(ROOT / "emane" / "results" / "E1_optimized" / "results" / "schedule.xml"),
        "{{PLATFORM_06}}": code(ROOT / "emane" / "results" / "E1_optimized" / "scenario" / "platform-06.xml"),
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text


def find_browser() -> str:
    for b in BROWSERS:
        if Path(b).exists() or shutil.which(b):
            return b
    raise SystemExit("no Chromium-based browser found for HTML -> PDF")


def main() -> int:
    BUILD.mkdir(exist_ok=True)
    md_text = fill_placeholders((DOCS / "Documentation.md").read_text(encoding="utf-8"))
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "md_in_html", "sane_lists"])
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>TDMA Schedule Planner &amp; "
            f"Optimizer - Documentation</title><base href='{DOCS.as_uri()}/'><style>{CSS}</style>"
            f"</head><body>{body}</body></html>")
    html_path = BUILD / "Documentation.html"
    html_path.write_text(page, encoding="utf-8")
    pdf_path = DOCS / "Documentation.pdf"
    browser = find_browser()
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
           f"--print-to-pdf={pdf_path}", html_path.as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    print(f"wrote {pdf_path} ({pdf_path.stat().st_size // 1024} KB) using {Path(browser).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
