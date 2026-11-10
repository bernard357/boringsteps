import { defineConfig, type HeadConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import footnote from 'markdown-it-footnote'
import taskLists from 'markdown-it-task-lists'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import sharp from 'sharp'

const SITE_URL = 'https://boringsteps.org'
const SITE_NAME = 'Boring steps'
const SITE_DESCRIPTION =
  'A blog and book about building simple, durable systems on purpose.'

// Single source of truth for the publisher identity, reused by the JSON-LD
// Organization/WebSite/Article blocks. Defined once here so adding a post or a
// social profile is a one-line change, not a per-page edit.
const IDENTITY = {
  name: SITE_NAME,
  url: `${SITE_URL}/`,
  logo: `${SITE_URL}/logo.svg`,
  sameAs: ['https://github.com/bernard357/boringsteps'],
}

// The person behind every post. LinkedIn's Post Inspector reports "No author
// found" without <meta name="author">; the profile URL feeds article:author
// and the JSON-LD Person.
const AUTHOR = {
  name: 'Bernard Paques',
  url: 'https://www.linkedin.com/in/webnetworker',
}

// Comments widget settings, read from the build environment (outputs of the
// comments/ SAM stack). Injected through vite.define as __COMMENTS__ so the
// values land in the JS bundle only: themeConfig is inlined into every HTML
// page as __VP_SITE_DATA__. Left empty, the widget renders nothing.
const COMMENTS = {
  apiUrl: process.env.VITE_COMMENTS_API_URL ?? '',
  cognitoDomain: process.env.VITE_COMMENTS_COGNITO_DOMAIN ?? '',
  clientId: process.env.VITE_COMMENTS_CLIENT_ID ?? '',
}

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

// Social card limits. LinkedIn wants about 1.91:1 and at least 1200 px wide;
// narrower images are shrunk to a small thumbnail.
const CARD_MIN_WIDTH = 1200
const CARD_MIN_RATIO = 1.8
const CARD_MAX_RATIO = 2.0

type SocialImage = { url: string; width?: number; height?: number }

// Resolve a frontmatter `image` to an absolute URL, plus its pixel size when
// it is a local file under public/. Throws, failing the build, when a local
// card is missing or badly sized, so a cropped or tiny preview is caught here
// and not on LinkedIn. An absolute URL cannot be read: the author owns it.
async function socialImage(image: string, page: string): Promise<SocialImage> {
  if (/^https:\/\//.test(image)) return { url: image }
  const path = image.startsWith('/') ? image : `/${image}`
  const file = join(DOCS, 'public', path)
  let width: number | undefined
  let height: number | undefined
  try {
    const meta = await sharp(file).metadata()
    width = meta.width
    height = meta.height
  } catch {
    throw new Error(`${page}: image "${image}" not found at ${file}`)
  }
  if (!width || !height) throw new Error(`${page}: cannot read size of "${image}"`)
  const ratio = width / height
  if (width < CARD_MIN_WIDTH || ratio < CARD_MIN_RATIO || ratio > CARD_MAX_RATIO) {
    throw new Error(
      `${page}: image "${image}" is ${width}x${height}; ` +
        `need at least ${CARD_MIN_WIDTH} px wide and an aspect ratio of ` +
        `${CARD_MIN_RATIO} to ${CARD_MAX_RATIO} (1200x630 is ideal)`,
    )
  }
  return { url: `${SITE_URL}${path}`, width, height }
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
    define: {
      __COMMENTS__: JSON.stringify(COMMENTS),
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
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
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
  async transformPageData(pageData) {
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

    // Page-specific social card. Same property as the site default, so
    // VitePress lets this one win; without `image`, the default stays.
    if (typeof fm.image === 'string' && fm.image) {
      const card = await socialImage(fm.image, pageData.relativePath)
      const alt = (typeof fm.image_alt === 'string' && fm.image_alt) || title
      head.push(
        ['meta', { property: 'og:image', content: card.url }],
        ['meta', { property: 'og:image:alt', content: alt }],
        ['meta', { name: 'twitter:image', content: card.url }],
        ['meta', { name: 'twitter:image:alt', content: alt }],
        ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
      )
      if (card.width && card.height) {
        head.push(
          ['meta', { property: 'og:image:width', content: String(card.width) }],
          ['meta', { property: 'og:image:height', content: String(card.height) }],
        )
      }
    }

    // Structured data for search engines and answer engines. Site-level
    // Organization + WebSite on every page; an Article block on posts (pages
    // carrying a date). VitePress renders a head script from the tuple
    // ['script', attrs, innerHTML], so the JSON-LD is stringified into the
    // third slot.
    const graph: Record<string, unknown>[] = [
      {
        '@type': 'Organization',
        '@id': `${SITE_URL}/#organization`,
        name: IDENTITY.name,
        url: IDENTITY.url,
        logo: IDENTITY.logo,
        sameAs: IDENTITY.sameAs,
      },
      {
        '@type': 'WebSite',
        '@id': `${SITE_URL}/#website`,
        name: IDENTITY.name,
        url: IDENTITY.url,
        description: SITE_DESCRIPTION,
        publisher: { '@id': `${SITE_URL}/#organization` },
      },
    ]
    if (isPost) {
      // VitePress parses a YAML `date:` into a JS Date; schema.org wants an
      // ISO-8601 date string (YYYY-MM-DD), so normalize rather than stringify.
      const published = new Date(fm.date as string | number | Date)
        .toISOString()
        .slice(0, 10)
      head.push(
        ['meta', { name: 'author', content: AUTHOR.name }],
        ['meta', { property: 'article:author', content: AUTHOR.url }],
        ['meta', { property: 'article:published_time', content: published }],
      )
      for (const tag of Array.isArray(fm.tags) ? fm.tags : []) {
        head.push(['meta', { property: 'article:tag', content: String(tag) }])
      }
      graph.push({
        '@type': 'Article',
        headline: title,
        description,
        datePublished: published,
        dateModified: published,
        author: { '@type': 'Person', name: AUTHOR.name, url: AUTHOR.url },
        publisher: { '@id': `${SITE_URL}/#organization` },
        mainEntityOfPage: url,
      })
    }
    const jsonLd = JSON.stringify({ '@context': 'https://schema.org', '@graph': graph })
    head.push(['script', { type: 'application/ld+json' }, jsonLd])

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
