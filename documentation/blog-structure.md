---
state: production
layout: doc
eyebrow: reference
---

# Blog structure

How posts are authored, addressed, and indexed on **Boring steps**. Posts
are independent essays; the only thing they share is the boring principle.

## Flat URLs and deep linking

Each post is a single Markdown file at the **root** of the docs tree:

```
documentation/<slug>.md   →   https://boringsteps.org/<slug>
```

There is no `/blog` segment. The flat `/<slug>` URL is the post's permanent
address, so external references stay valid indefinitely. Do not rename a
published slug.

## Post frontmatter

A page is treated as a **post** (rather than a plain site page like `about`)
when it carries a `date:` field. Posts use the default VitePress `doc` layout,
so do not set a `layout:` key. Minimum frontmatter:

```yaml
---
title: Hello, boring world
date: 2026-10-14
tags: [meta, principles]
excerpt: Why this blog exists and what "boring by design" means.
---
```

| Field | Required | Purpose |
| --- | --- | --- |
| `title` | yes | Post title, shown in the index and the page |
| `date` | yes | Publication date (`YYYY-MM-DD`); also the post marker |
| `tags` | no | List of keywords, shown on the post and index |
| `excerpt` | no | One-line summary; falls back to the first paragraph |

Do not set `layout:` on a post — VitePress has no `post` layout, and naming a
nonexistent layout renders a blank page. The `date:` field alone marks a post.

## The posts index

At build time, `scripts/build_posts.py` scans every root `documentation/*.md`
carrying a `date:`, reads its frontmatter and first paragraph, and writes a
newest-first JSON index to `documentation/public/posts.json`:

```json
[
  {
    "title": "Hello, boring world",
    "url": "/hello-boring-world",
    "date": "2026-10-14",
    "tags": ["meta", "principles"],
    "excerpt": "Why this blog exists and what \"boring by design\" means."
  }
]
```

The file ships to `dist/posts.json` and the home page fetches it in the
browser to render the recent-posts list. It is build-generated, so it is
git-ignored and regenerated on every `make build`.

## Home, history, and navigation

The home page `/` does not hold content of its own: on load it resolves the
newest post from `posts.json` and redirects to that post's canonical `/<slug>`
URL, so the front door always reflects the most recent writing with no manual
edit. `/history` lists every post newest-first. Each post page carries a
data-driven previous/next bar (older/newer in publication order), computed from
`posts.json`; on the newest post the "older" link is the previous-post
navigation.

## Atom feed

`scripts/build_posts.py` also emits `documentation/public/atom.xml`, a valid
Atom 1.0 feed with one entry per post (newest-first). Absolute URLs are built
from the domain in `documentation/public/CNAME`, so the feed stays correct
across a domain change. The feed is build-generated (git-ignored) and
discoverable via a `<link rel="alternate" type="application/atom+xml">` tag and
a feed icon in the top navigation.

## Publication states

Whether a page reaches the production site is governed by its frontmatter
`state` and the `MATCHING_STATES` build variable — a fail-closed allow-list.

- The GitHub Actions build sets `MATCHING_STATES: production`. A page is
  published **only if** its `state` is in that comma-separated list.
- A page with **no `state`**, or a non-matching one, is **excluded** from the
  production build. Publishing is therefore a conscious act: add
  `state: production`.
- `state: local` marks a page as local-only (e.g. `rendering-test.md`); it is
  visible under `make serve`/`make build` but never shipped.
- When `MATCHING_STATES` is unset (local builds), nothing is filtered, so every
  page — including drafts and local-only pages — is visible.

The filter lives in `.vitepress/config.mts`, which scans page frontmatter and
adds non-matching pages to `srcExclude` at build time.

## From blog to book

When there is enough material, the same post files become book chapters with
only a sidebar change: add an ordered `sidebar` grouping in
`.vitepress/config.mts` over the chosen posts. No content moves, no URL
changes — the blog is a flat list over the posts, the book is an ordered path
through them.
