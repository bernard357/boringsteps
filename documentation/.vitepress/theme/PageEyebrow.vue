<script setup>
import { computed } from 'vue'
import { useData } from 'vitepress'

const { frontmatter, page } = useData()

// Show a colored uppercase eyebrow above the title on content pages only.
// Skip the home redirect shim and the history index (no article title).
const skipped = ['index.md', 'history.md']
const show = computed(() => !skipped.includes(page.value.relativePath))
const eyebrow = computed(() => frontmatter.value.eyebrow || 'article')
</script>

<template>
  <span v-if="show" class="page-eyebrow">{{ eyebrow }}</span>
</template>
