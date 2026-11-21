"""Idempotent, marker-delimited sections inside docs/TIGER_DATA_RESULTS.md.

Each benchmark owns one section; re-running replaces only its own section.
"""
from pathlib import Path

TITLE = "# Tiger Data results\n"


def upsert_section(path: Path, key: str, heading: str, body: str) -> None:
    start, end = f"<!-- section:{key}:start -->", f"<!-- section:{key}:end -->"
    block = f"{start}\n## {heading}\n\n{body.strip()}\n{end}\n"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if start in text and end in text:
        a, b = text.index(start), text.index(end) + len(end)
        text = text[:a] + block.rstrip("\n") + text[b:]
    else:
        if "<!-- section:" not in text:
            text = ""  # legacy single-benchmark document: replaced by sectioned layout
        text = (text.rstrip() + "\n\n" if text else TITLE + "\n") + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
