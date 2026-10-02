<script setup>
import { computed } from 'vue'
import { useData, withBase } from 'vitepress'
import { data as posts } from '../../posts.data.mjs'
const { page } = useData()
const post = computed(() => posts.find(p => p.url === `/${page.value.relativePath.replace(/\.md$/, '.html')}`))
</script>
<template>
  <div v-if="post" class="article-meta" aria-label="文章信息">
    <span class="category-mark">{{ post.category }}</span><time :datetime="post.date">{{ post.date }}</time><span>约 {{ post.minutes }} 分钟</span>
    <div class="article-tags"><a v-for="tag in post.tags" :key="tag" :href="withBase(`/tags.html#${encodeURIComponent(tag)}`)">{{ tag }}</a></div>
  </div>
</template>
