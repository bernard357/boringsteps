---
state: production
layout: doc
aside: false
outline: false
sidebar: false
eyebrow: Boring Steps
---

# Past content

<script setup>
import { ref, onMounted } from 'vue'
import { withBase } from 'vitepress'

const posts = ref([])

onMounted(async () => {
  const res = await fetch(withBase('/posts.json'))
  posts.value = await res.json()
})

function href(url) {
  return withBase(url)
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}
</script>

<div class="post-list">
  <article v-for="post in posts" :key="post.url" class="post-item">
    <h3 class="post-title"><a :href="href(post.url)">{{ post.title }}</a></h3>
    <p class="post-meta">
      <time :datetime="post.date">{{ formatDate(post.date) }}</time>
      <span v-if="post.tags && post.tags.length" class="post-tags">
        <span v-for="tag in post.tags" :key="tag" class="post-tag">{{ tag }}</span>
      </span>
    </p>
    <p class="post-excerpt">{{ post.excerpt }}</p>
  </article>
  <p v-if="!posts.length" class="post-empty">No posts yet.</p>
</div>
