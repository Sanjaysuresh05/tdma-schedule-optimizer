"""Regenerate every file in outputs/ by running the CLI on every inputs/*.json.

For each topology X:
    X_report.txt    default CLI output (the mandated report)
    X_detailed.txt  --verbose --max-reuse --simulate 100
    X_schedule.json --json-out (consumed by the EMANE bridge)
"""

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tdma_brain.cli import main  # noqa: E402

OUT = ROOT / "outputs"


def capture(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = main(argv)
    return code, buf.getvalue()


def run() -> None:
    for f in sorted((ROOT / "inputs").glob("*.json")):
        name = f.stem
        code, text = capture([f.read_text().strip()])
        (OUT / f"{name}_report.txt").write_text(text, encoding="utf-8")
        code2, text2 = capture(["--file", str(f), "--verbose", "--max-reuse", "--simulate", "100",
                                "--json-out", str(OUT / f"{name}_schedule.json")])
        (OUT / f"{name}_detailed.txt").write_text(text2, encoding="utf-8")
        k = next(l for l in text.splitlines() if l.startswith("Optimized Frame Length"))
        print(f"{name:<14} exit={code}/{code2}  {k}")


if __name__ == "__main__":
    run()
