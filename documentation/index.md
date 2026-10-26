---
state: production
layout: doc
aside: false
outline: false
sidebar: false
excerpt: A blog and book about building simple, durable systems on purpose.
---

<script setup>
import { onMounted } from 'vue'
import { useRouter, withBase } from 'vitepress'
// Imported at build time so the post list is server-rendered into the static
// HTML. Non-JS crawlers and agents read the full list below; JS readers are
// redirected to the latest post on mount.
import posts from './public/posts.json'

const latest = posts[0]

const router = useRouter()

onMounted(() => {
  // Home reflects the most recent post: send the reader to its canonical URL.
  if (latest) router.go(withBase(latest.url))
})
</script>

<div class="home-redirect">
  <p v-if="latest">Taking you to the latest post…
    <a :href="withBase(latest.url)">{{ latest.title }}</a>
  </p>
  <p v-else>
    No posts yet — browse the <a :href="withBase('/history')">history</a>.
  </p>

  <h1>Boring steps</h1>
  <p>A blog and book about building simple, durable systems on purpose. Browse the latest posts below, or see the full <a :href="withBase('/history')">history</a>.</p>

  <ul class="home-post-list">
    <li v-for="post in posts" :key="post.url">
      <a :href="withBase(post.url)">{{ post.title }}</a>
      <span class="home-post-date">{{ post.date }}</span>
      <p class="home-post-excerpt">{{ post.excerpt }}</p>
    </li>
  </ul>
</div>
