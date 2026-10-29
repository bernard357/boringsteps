#!/usr/bin/env python3
"""Build the blog index for Boring steps.

Scans every root documentation/*.md carrying a ``date:`` field, reads its
frontmatter and first paragraph, and writes a newest-first JSON index to
documentation/public/posts.json.

Standard library only — post frontmatter is a small, known subset of YAML
(scalars plus an inline ``tags: [a, b]`` list), so no PyYAML dependency.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "documentation"
PUBLIC = DOCS / "public"
OUT = PUBLIC / "posts.json"
FEED = PUBLIC / "atom.xml"
LLMS = PUBLIC / "llms.txt"
CNAME = PUBLIC / "CNAME"

SITE_TITLE = "Boring steps"

# Pages that are never posts even if edited to carry a date.
EXCLUDE = {
    "index.md",
    "about.md",
    "blog-structure.md",
    "identity.md",
    "history.md",
    "rendering-test.md",
}

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def parse_scalar(value: str) -> object:
    """Parse a frontmatter scalar or inline list into a Python value."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    return value.strip("\"'")


def parse_frontmatter(block: str) -> dict[str, object]:
    """Parse the simple key: value frontmatter subset used by posts."""
    data: dict[str, object] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        data[key.strip()] = parse_scalar(raw)
    return data


def first_paragraph(body: str) -> str:
    """Return the first non-heading, non-empty paragraph of the body."""
    paragraph: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("#"):
            continue
        paragraph.append(stripped)
    return " ".join(paragraph)


def collect_posts() -> list[dict[str, object]]:
    posts: list[dict[str, object]] = []
    for path in sorted(DOCS.glob("*.md")):
        if path.name in EXCLUDE:
            continue
        match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            continue
        meta = parse_frontmatter(match.group(1))
        if "date" not in meta:
            continue
        slug = path.stem
        posts.append(
            {
                "title": meta.get("title", slug),
                "url": f"/{slug}",
                "date": meta.get("date", ""),
                "tags": meta.get("tags", []),
                "excerpt": meta.get("excerpt") or first_paragraph(match.group(2)),
            }
        )
    posts.sort(key=lambda p: str(p["date"]), reverse=True)
    return posts


def site_base() -> str:
    """Canonical site URL from the CNAME file, falling back to the apex."""
    domain = "boringsteps.org"
    if CNAME.exists():
        value = CNAME.read_text(encoding="utf-8").strip()
        if value:
            domain = value
    return f"https://{domain}"


def to_rfc3339(date: str) -> str:
    """Turn a YYYY-MM-DD date into an RFC 3339 timestamp for Atom."""
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.isoformat()


def build_atom(posts: list[dict[str, object]], base: str) -> str:
    """Render a minimal, valid Atom 1.0 feed for the posts (newest-first)."""
    updated = to_rfc3339(str(posts[0]["date"])) if posts else datetime.now(
        timezone.utc
    ).isoformat()
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{escape(SITE_TITLE)}</title>",
        f'  <link href="{base}/"/>',
        f'  <link rel="self" href="{base}/atom.xml"/>',
        f"  <id>{base}/</id>",
        f"  <updated>{updated}</updated>",
    ]
    for post in posts:
        url = f"{base}{post['url']}"
        lines += [
            "  <entry>",
            f"    <title>{escape(str(post['title']))}</title>",
            f'    <link href="{url}"/>',
            f"    <id>{url}</id>",
            f"    <updated>{to_rfc3339(str(post['date']))}</updated>",
            f"    <summary>{escape(str(post['excerpt']))}</summary>",
            "  </entry>",
        ]
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def build_llms_txt(posts: list[dict[str, object]], base: str) -> str:
    """Render a minimal llms.txt: site summary plus a list of posts.

    Generated from the same parsed posts as posts.json so the AI-navigation
    file never drifts from the published set. Follows the llms.txt convention
    of an H1 title, a blockquote summary, and a linked section of resources.
    """
    lines = [
        f"# {SITE_TITLE}",
        "",
        "> A blog and book about building simple, durable systems on purpose.",
        "",
        "## Posts",
        "",
    ]
    for post in posts:
        url = f"{base}{post['url']}"
        excerpt = str(post.get("excerpt", "")).strip()
        suffix = f": {excerpt}" if excerpt else ""
        lines.append(f"- [{post['title']}]({url}){suffix}")
    return "\n".join(lines) + "\n"


def main() -> None:
    posts = collect_posts()
    base = site_base()
    PUBLIC.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(posts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    FEED.write_text(build_atom(posts, base), encoding="utf-8")
    LLMS.write_text(build_llms_txt(posts, base), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)}, {FEED.relative_to(ROOT)}, and "
        f"{LLMS.relative_to(ROOT)} with {len(posts)} post(s)"
    )


if __name__ == "__main__":
    main()
