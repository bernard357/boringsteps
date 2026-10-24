---
state: production
eyebrow: reference
---

# Visual identity

The visual identity for **Boring steps** is deliberately restrained. The
site argues for simple, durable systems, so its look earns trust through
clarity rather than decoration: a quiet neutral base, one reserved accent, a
readable serif for prose, and a single geometric mark.

## Concept

The brand mark is a 3×3 grid of rounded squares with eight outlined and the
bottom-right one filled in the accent colour. It reads as *structure with one
deliberate choice* — the essence of designing by convention. The mark scales
from a 16px favicon to the hero without losing meaning, and pairs with a plain
serif wordmark: "Boring" in ink, "by design" in the accent.

## Palette

Ink/slate neutrals carry the page; a single muted green is the only accent,
used for links, the filled grid cell, and the pre-header eyebrow.

| Role | Light | Dark |
| --- | --- | --- |
| Background | `#f7f8fa` | `#15191e` |
| Surface | `#ffffff` | `#1e242b` |
| Body text | `#1a2733` | `#d6dde4` |
| Muted text | `#5b6b7a` | `#9aa7b4` |
| Accent (brand 1) | `#1f7a45` | `#5bbd84` |
| Accent hover (brand 2) | `#19633a` | `#7cc99a` |

### Contrast

Measured WCAG 2.1 contrast ratios against the page background. Body text and
the accent both clear the AA threshold (4.5:1 for normal text) in both themes.

| Pair | Ratio | AA (4.5:1) |
| --- | --- | --- |
| Light body `#1a2733` on `#f7f8fa` | 14.30:1 | pass |
| Light accent `#1f7a45` on `#f7f8fa` | 5.03:1 | pass |
| Dark body `#d6dde4` on `#15191e` | 12.88:1 | pass |
| Dark accent `#5bbd84` on `#15191e` | 7.61:1 | pass |

## Typography

One serif family is used for both body and headings, for a quiet, uniform page
(no separate sans for chrome).

- **Body and headings:** Georgia, Cambria, "Times New Roman", serif
- **Code:** ui-monospace, "SF Mono", Menlo, monospace

## Pre-header eyebrow

Each content page shows a small uppercase eyebrow in the accent colour above
its title, read from a frontmatter `eyebrow` field and defaulting to `article`
when absent. It is rendered by the `doc-before` theme slot and skipped on the
home redirect and the history index.

## Logo usage

- `public/logo.svg` — ink stroke, for light backgrounds.
- `public/logo-dark.svg` — light stroke, for dark backgrounds; VitePress swaps
  automatically when both are configured.
- Keep clear space around the mark equal to one grid cell. Do not recolour the
  outlined cells or move the filled cell. Minimum size 16px.

## Derived assets

All raster assets derive from the SVG mark through `scripts/generate-assets.mjs`
(run with `npm run assets`): the favicon set, the Apple touch icon, and the
1200×630 Open Graph card. Regenerate them whenever the mark or palette changes.
