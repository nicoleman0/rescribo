"""Resolve append-only merge conflicts by keeping both sides, upstream first.

Use only on files where parallel branches each append their own section, such
as frontend/DESIGN.md and openspec/specs/*/spec.md.
Usage: python3 union-resolve.py <file>...
"""

import re
import sys

for path in sys.argv[1:]:
    with open(path) as handle:
        text = handle.read()
    text = re.sub(
        r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n",
        lambda match: match.group(1).rstrip("\n") + "\n\n" + match.group(2),
        text,
        flags=re.S,
    )
    if "<<<<<<<" in text or ">>>>>>>" in text:
        sys.exit(f"{path}: a conflict is not a plain two-sided append")
    with open(path, "w") as handle:
        handle.write(text)
