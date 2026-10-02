<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { withBase } from 'vitepress'
import { VPButton } from 'vitepress/theme'
import { data as posts } from '../../posts.data.mjs'
const props = defineProps({ mode: { type: String, default: 'category' } })
const selected = ref('全部')
const filters = computed(() => ['全部', ...new Set(posts.flatMap(p => props.mode === 'tags' ? p.tags : [p.category]))])
const visible = computed(() => posts.filter(p => selected.value === '全部' || (props.mode === 'tags' ? p.tags.includes(selected.value) : p.category === selected.value)))
function readHash() {
  if (props.mode !== 'tags') return
  let tag = ''; try { tag = decodeURIComponent(window.location.hash.slice(1)) } catch {}
  selected.value = filters.value.includes(tag) ? tag : '全部'
}
function select(filter) {
  selected.value = filter
  if (props.mode === 'tags') window.history.replaceState(null, '', filter === '全部' ? window.location.pathname : `#${encodeURIComponent(filter)}`)
}
onMounted(() => { readHash(); window.addEventListener('hashchange', readHash) })
onUnmounted(() => { window.removeEventListener('hashchange', readHash) })
</script>
<template>
  <div class="post-listing">
    <div class="filter-list" :aria-label="mode === 'tags' ? '按标签筛选' : '按主题筛选'"><VPButton v-for="filter in filters" :key="filter" type="button" :theme="selected === filter ? 'brand' : 'alt'" :aria-pressed="selected === filter" :text="filter" @click="select(filter)" /></div>
    <p class="result-count" aria-live="polite">共 {{ visible.length }} 篇笔记</p>
    <article v-for="post in visible" :key="post.url" class="list-post">
      <div class="list-meta"><span>{{ post.category }}</span><time :datetime="post.date">{{ post.date }}</time><span>约 {{ post.minutes }} 分钟</span></div>
      <h2><a :href="withBase(post.url)">{{ post.title }}</a></h2><p>{{ post.description }}</p>
      <div class="list-tags"><a v-for="tag in post.tags" :key="tag" :href="withBase(`/tags.html#${encodeURIComponent(tag)}`)">{{ tag }}</a></div>
    </article>
  </div>
</template>

<style scoped>
.filter-list, .list-meta, .list-tags { display: flex; flex-wrap: wrap; gap: 12px; }
.filter-list { margin: 24px 0; }
.list-meta, .result-count, .list-tags { color: var(--vp-c-text-2); font-size: 14px; }
.list-post { margin: 32px 0; }
</style>
