"""Build a before/after comparison page from two screenshot folders.

Usage: python3 .claude/skills/work-issues/scripts/compare.py spec.json out.html
spec.json: {"before": dir, "after": dir, "title": str, "heading": str,
            "intro": str, "meta": str,
            "screens": [[shot-name, caption, note], ...]}
shot-name is a file stem from shots.mjs, e.g. "inbox-report-desktop-dark".
"""

import base64
import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text())
tmp = Path(tempfile.mkdtemp())


def img(directory: str, name: str) -> str:
    src = Path(directory) / f"{name}.png"
    out = tmp / f"{Path(directory).name}-{name}.jpg"
    width = "390" if "phone" in name else "1100"
    subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            "62",
            "--resampleWidth",
            width,
            str(src),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return "data:image/jpeg;base64," + base64.b64encode(out.read_bytes()).decode()


e = html.escape


def figure(side: str, src: str, title: str) -> str:
    label = side.capitalize()
    return (
        f'<figure><figcaption><span class="tag {side}">{label}</span></figcaption>'
        f'<img loading="lazy" src="{src}" alt="{e(title)} {side}"></figure>'
    )


nav = "".join(f'<li><a href="#{k}">{e(t)}</a></li>' for k, t, _ in spec["screens"])
sections = ""
for key, title, note in spec["screens"]:
    phone = " phone" if "phone" in key else ""
    note_html = f"<p>{e(note)}</p>" if note else ""
    sections += f"""<section id="{key}" class="shot{phone}">
  <header><h2>{e(title)}</h2>{note_html}</header>
  <div class="pair">
    {figure("before", img(spec["before"], key), title)}
    {figure("after", img(spec["after"], key), title)}
  </div>
</section>
"""

style = (Path(__file__).parent / "compare.css").read_text()

page = f"""<title>{e(spec["title"])}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{style}</style>
<div class="wrap">
  <div class="intro">
    <h1>{e(spec["heading"])}</h1>
    <p>{e(spec["intro"])}</p>
    <span class="mono">{e(spec["meta"])}</span>
  </div>
  <nav aria-label="Screens"><ul>{nav}</ul></nav>
  {sections}
</div>
"""
Path(sys.argv[2]).write_text(page)
print(len(page))
