import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { h, resolveComponent } from 'vue'
import PageComments from './PageComments.vue'
import PostNav from './PostNav.vue'
import PageEyebrow from './PageEyebrow.vue'
import SiteFooter from './SiteFooter.vue'
import './custom.css'

// Extend the VitePress default theme with the Boring steps identity.
// Keeping the default theme (rather than forking it) means the brand lives
// entirely in custom.css and survives VitePress upgrades. Slots:
//   doc-before    — colored uppercase eyebrow above the title (PageEyebrow)
//   doc-after     — data-driven previous/next bar below a post (PostNav), then
//                   the comments widget (PageComments), client-only so the
//                   server-rendered HTML carries no comment markup
//   layout-bottom — two-part site footer (SiteFooter)
export default {
  extends: DefaultTheme,
  Layout() {
    // VitePress registers ClientOnly globally but does not export it.
    const ClientOnly = resolveComponent('ClientOnly')
    return h(DefaultTheme.Layout, null, {
      'doc-before': () => h(PageEyebrow),
      'doc-after': () => [
        h(PostNav),
        h(ClientOnly, null, { default: () => h(PageComments) }),
      ],
      'layout-bottom': () => h(SiteFooter),
    })
  },
} satisfies Theme
