import { defineConfig, type HeadConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import footnote from 'markdown-it-footnote'
import taskLists from 'markdown-it-task-lists'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SITE_URL = 'https://boringsteps.org'
const SITE_DESCRIPTION =
  'A blog and book about building simple, durable systems on purpose.'

// documentation/ root, so file reads below resolve against it.
const DOCS = dirname(dirname(fileURLToPath(import.meta.url)))

// First non-heading, non-empty paragraph of a page body. Mirrors the excerpt
// fallback in scripts/build_posts.py so the two stay consistent; this hook
// runs in TypeScript at build time and cannot import that Python logic.
function firstParagraph(relativePath: string): string {
  let text: string
  try {
    text = readFileSync(join(DOCS, relativePath), 'utf-8')
  } catch {
    return ''
  }
  const body = text
    .replace(/^---\n[\s\S]*?\n---\n?/, '') // frontmatter
    .replace(/<script[\s\S]*?<\/script>/gi, '') // Vue <script setup> blocks
    .replace(/<style[\s\S]*?<\/style>/gi, '') // style blocks
    .replace(/<!--[\s\S]*?-->/g, '') // HTML comments
    .replace(/^```[\s\S]*?^```/gm, '') // fenced code blocks
  const paragraph: string[] = []
  for (const line of body.split('\n')) {
    const stripped = line.trim()
    if (!stripped) {
      if (paragraph.length) break
      continue
    }
    if (stripped.startsWith('#') || stripped.startsWith('<')) continue
    paragraph.push(stripped)
  }
  return paragraph.join(' ')
}

// Absolute clean URL for a page, e.g. "duckdb-vectors.md" -> site/duckdb-vectors,
// "index.md" -> site/. Matches VitePress cleanUrls output.
function canonicalUrl(relativePath: string): string {
  const path = relativePath.replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, '')
  return `${SITE_URL}/${path}`.replace(/\/$/, path ? '' : '/')
}

// Fail-closed state filter. A page is published only when its frontmatter
// `state` is in MATCHING_STATES (set in CI, e.g. "production"). Pages with no
// `state`, or a non-matching one, are excluded. When MATCHING_STATES is unset
// (local builds), nothing is filtered, so every page is visible.
function stateExcludes(): string[] {
  const allowed = (process.env.MATCHING_STATES ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  if (!allowed.length) return [] // unset → no filtering (local)

  // srcDir is this file's parent's parent (the documentation/ root), so the
  // returned globs are relative to it: "<name>.md", never "documentation/...".
  const docs = dirname(dirname(fileURLToPath(import.meta.url)))
  const excluded: string[] = []
  for (const name of readdirSync(docs)) {
    if (!name.endsWith('.md')) continue
    const text = readFileSync(join(docs, name), 'utf-8')
    const fm = text.match(/^---\n([\s\S]*?)\n---/)
    const state = fm?.[1].match(/^state:\s*(.+)$/m)?.[1].trim().replace(/^["']|["']$/g, '')
    if (!state || !allowed.includes(state)) excluded.push(name)
  }
  return excluded
}

// https://vitepress.dev/reference/site-config
export default withMermaid(defineConfig({
  srcExclude: stateExcludes(),
  // Pre-bundle Mermaid's CommonJS dependencies so the Vite dev server resolves
  // their ESM interop; without this, `fastdom` throws "does not provide an
  // export named 'default'" and the dev page renders blank. The production
  // (Rollup) build already handles this, so it only affects `make serve`.
  vite: {
    optimizeDeps: {
      include: ['mermaid', 'dayjs', 'fastdom', 'cytoscape'],
    },
  },
  markdown: {
    // Enable GFM features VitePress omits by default.
    config: (md) => {
      md.use(footnote)
      md.use(taskLists)
    },
  },
  title: 'Boring steps',
  description: SITE_DESCRIPTION,
  // Served from the custom apex domain boringsteps.org at the root.
  base: '/',
  lang: 'en-US',
  cleanUrls: true,
  lastUpdated: true,
  sitemap: { hostname: SITE_URL },
  head: [
    ['link', { rel: 'icon', href: '/favicon.ico', sizes: 'any' }],
    ['link', { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' }],
    ['link', { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/favicon-16x16.png' }],
    ['link', { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' }],
    ['meta', { name: 'theme-color', content: '#1f7a45' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Boring steps' }],
    ['meta', { property: 'og:description', content: SITE_DESCRIPTION }],
    ['meta', { property: 'og:url', content: `${SITE_URL}/` }],
    ['meta', { property: 'og:image', content: `${SITE_URL}/og-image.png` }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'Boring steps' }],
    ['meta', { name: 'twitter:description', content: SITE_DESCRIPTION }],
    ['meta', { name: 'twitter:image', content: `${SITE_URL}/og-image.png` }],
    ['link', { rel: 'alternate', type: 'application/atom+xml', title: 'Boring steps', href: '/atom.xml' }],
  ],
  // Per-page SEO/GEO metadata. The static head array above carries site-level
  // defaults; here we push page-specific tags onto frontmatter.head so each
  // page gets its own description, canonical, and Open Graph/Twitter values.
  // Non-JS crawlers and answer engines read these from the server-rendered HTML.
  transformPageData(pageData) {
    const fm = pageData.frontmatter
    const isPost = Boolean(fm.date)
    const title = pageData.title || 'Boring steps'
    const description =
      (typeof fm.excerpt === 'string' && fm.excerpt) ||
      firstParagraph(pageData.relativePath) ||
      SITE_DESCRIPTION
    const url = canonicalUrl(pageData.relativePath)

    // Drive the <meta name="description"> VitePress renders from pageData,
    // instead of appending a second, conflicting description tag to head.
    pageData.description = description

    const head: HeadConfig[] = [
      ['link', { rel: 'canonical', href: url }],
      ['meta', { property: 'og:type', content: isPost ? 'article' : 'website' }],
      ['meta', { property: 'og:title', content: title }],
      ['meta', { property: 'og:description', content: description }],
      ['meta', { property: 'og:url', content: url }],
      ['meta', { name: 'twitter:title', content: title }],
      ['meta', { name: 'twitter:description', content: description }],
    ]

    fm.head = [...(fm.head ?? []), ...head]
  },
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: { light: '/logo.svg', dark: '/logo-dark.svg', alt: 'Boring steps' },
    nav: [
      { text: 'History', link: '/history' },
      { text: 'About', link: '/about' },
    ],
    // No sidebar for now — posts are flat and independent. When enough
    // material accumulates, add an ordered sidebar grouping here to turn
    // the blog into a book without moving any files.
    sidebar: false,
    search: {
      provider: 'local',
    },
    socialLinks: [
      {
        icon: {
          svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4 11a9 9 0 0 1 9 9h2.5A11.5 11.5 0 0 0 4 8.5V11zm0 4a5 5 0 0 1 5 5h2.5A7.5 7.5 0 0 0 4 12.5V15zm1.5 5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"/></svg>',
        },
        link: '/atom.xml',
        ariaLabel: 'Atom feed',
      },
    ],
  },
}))
