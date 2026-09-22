#!/usr/bin/env python3
"""Reject colour literals outside the frontend theme file."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
THEME = FRONTEND / "src/styles/theme.css"

# These are the source formats where UI colour literals can be introduced.
TEXT_SUFFIXES = {".css", ".html", ".js", ".jsx", ".md", ".ts", ".tsx"}
# Vendor packages, build output, and snapshots are not authored UI source.
IGNORED_PARTS = {"node_modules", "dist", "test-results", "playwright-report"}
# The theme file is the single authorised home for design colour values.
COLOUR_LITERAL = re.compile(
    r"(?<![A-Za-z0-9])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![A-Za-z0-9])"
    r"|\b(?:rgba?|hsla?|oklch)\s*\("
)
# Only arbitrary utility values that can encode a colour are rejected.
ARBITRARY_COLOUR = re.compile(
    r"(?:bg|text|border|outline|ring|fill|stroke|from|via|to|divide|accent|caret|shadow)-\["
    r"[^\]]*(?:#|rgba?\s*\(|hsla?\s*\(|oklch\s*\(|color-mix\s*\(|var\(--)[^\]]*\]"
)


def iter_source_files() -> Iterator[Path]:
    for path in FRONTEND.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path == THEME:
            continue
        yield path


def main() -> int:
    failures: list[str] = []
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if COLOUR_LITERAL.search(line) or ARBITRARY_COLOUR.search(line):
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

    if failures:
        print("Raw colour values must live in frontend/src/styles/theme.css:")
        print("\n".join(failures))
        return 1
    print("Raw-colour check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
