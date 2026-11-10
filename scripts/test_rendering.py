#!/usr/bin/env python3
"""Validate GFM + Mermaid rendering of the local rendering-test page.

Reads the built HTML at documentation/.vitepress/dist/rendering-test.html and
asserts that each Markdown and Mermaid feature produced the expected markup.
Run `make build` (or `make preview`) first so the page exists; this script
does not build. Exits non-zero if any check fails, so it doubles as a
non-regression gate.

Standard library only — assertions are substring/regex checks against the
rendered HTML, matching the forms VitePress + vitepress-plugin-mermaid emit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "documentation" / ".vitepress" / "dist" / "rendering-test.html"

# Each check: (label, predicate(html) -> bool). Forms confirmed against the
# actual VitePress build output.
CHECKS: list[tuple[str, "re.Pattern[str] | str"]] = [
    ("heading h1", r"<h1\b"),
    ("heading h2", r"<h2\b"),
    ("heading h3", r"<h3\b"),
    ("heading h4", r"<h4\b"),
    ("bold", r"<strong>"),
    ("italic", r"<em>"),
    ("strikethrough", r"<s>"),
    ("unordered list", r"<ul>"),
    ("ordered list", r"<ol>"),
    ("table", r"<table\b"),
    ("table head", r"<thead>"),
    ("table align left", r"text-align:left;"),
    ("table align center", r"text-align:center;"),
    ("table align right", r"text-align:right;"),
    ("blockquote", r"<blockquote>"),
    ("inline code", r"<code>"),
    ("fenced code (ts)", r"language-ts"),
    ("link", r'<a [^>]*href="/"'),
    ("reference link", r'href="https://github.com/bernard357/boringsteps"'),
    ("autolink", r'<a [^>]*href="https://boringsteps\.org"'),
    ("image", r'<img [^>]*src="/logo\.svg"'),
    # Footnotes must render as real references/definitions, not literal
    # [^note] text — assert the generated anchors, not a heading id.
    ("footnote reference", r'class="footnote-ref"'),
    ("footnote definition", r'id="fn1"'),
    ("footnote backref", r'href="#fnref1"'),
    ("horizontal rule", r"<hr\b"),
    # Mermaid: the plugin renders fences to a .mermaid wrapper containing SVG.
    ("mermaid blocks (2)", None),
    ("mermaid svg", r"<svg"),
    # GFM task list — VitePress does NOT render these by default; a passing
    # checkbox proves task-list support is enabled.
    ("task list checkbox", r'type="checkbox"'),
    # Social preview card read from the page frontmatter `image`.
    (
        "og:image absolute",
        r'<meta property="og:image" content="https://boringsteps\.org/social/rendering-test\.png">',
    ),
    ("og:image width", r'<meta property="og:image:width" content="1200">'),
    ("og:image height", r'<meta property="og:image:height" content="630">'),
    ("og:image alt", r'<meta property="og:image:alt" content="Rendering test social card">'),
    (
        "twitter:image",
        r'<meta name="twitter:image" content="https://boringsteps\.org/social/rendering-test\.png">',
    ),
    ("twitter:card large", r'<meta name="twitter:card" content="summary_large_image">'),
]


def run() -> int:
    if not PAGE.exists():
        print(f"ERROR: {PAGE.relative_to(ROOT)} not found — run `make build` first.")
        return 2
    html = PAGE.read_text(encoding="utf-8")

    passed, failed = [], []
    for label, pattern in CHECKS:
        if label == "mermaid blocks (2)":
            ok = len(re.findall(r'class="mermaid"', html)) >= 2
        else:
            ok = re.search(pattern, html) is not None
        (passed if ok else failed).append(label)

    for label in passed:
        print(f"  PASS  {label}")
    for label in failed:
        print(f"  FAIL  {label}")

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("Rendering regression: the features above did not render as expected.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
