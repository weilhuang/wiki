<script setup>
import { computed, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { renderMermaid } from '../mermaid-runtime.mjs'
const props = defineProps({ encoded: { type: String, required: true } })
const source = computed(() => decodeURIComponent(props.encoded))
const title = computed(() => source.value.match(/^\s*accTitle\s*:\s*(.+)$/m)?.[1] || '流程图')
const description = computed(() => source.value.match(/^\s*accDescr\s*:\s*(.+)$/m)?.[1] || '')
const container = ref(null), svg = ref(''), error = ref(false)
const id = `diagram-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
let observer, disposed = false, mounted = false, revision = 0
async function render() {
  observer?.disconnect()
  const request = ++revision
  try { const result = await renderMermaid(`${id}-${request}`, source.value); if (!disposed && request === revision) svg.value = result }
  catch (cause) { if (!disposed && request === revision) { error.value = true; console.error('Mermaid diagram failed:', title.value, cause) } }
}
watch(source, () => { if (mounted) { svg.value = ''; error.value = false; render() } })
onMounted(() => {
  mounted = true
  if ('IntersectionObserver' in window) { observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) render() }, { rootMargin: '400px' }); observer.observe(container.value) }
  else render()
})
onUnmounted(() => { disposed = true; revision++; observer?.disconnect() })
</script>
<template>
  <figure ref="container" class="mermaid-figure" :aria-label="title">
    <figcaption>{{ title }}</figcaption>
    <div v-if="svg" class="mermaid-canvas" tabindex="0" role="region" :aria-label="`${title}，可横向滚动查看完整图`" v-html="svg"></div>
    <p v-else-if="error" role="alert">图形暂时无法显示，请阅读下方文字说明与图源。</p>
    <p v-else class="diagram-loading">{{ description }}</p>
    <details class="diagram-source"><summary>文字说明与 Mermaid 图源</summary><p>{{ description }}</p><pre><code>{{ source }}</code></pre></details>
  </figure>
</template>
<style scoped>
.mermaid-figure { margin: 28px 0; }
figcaption { color: var(--vp-c-text-2); font-size: 14px; margin: 0 0 12px; }
.mermaid-canvas { overflow-x: auto; padding: 20px 12px; border: 1px solid var(--vp-c-divider); border-radius: 8px; background: #fff; text-align: center; }
.mermaid-canvas:focus-visible { outline: 2px solid var(--vp-c-brand-1); outline-offset: 3px; }
.mermaid-canvas :deep(svg) { display: inline-block; max-width: none; height: auto; vertical-align: middle; }
.mermaid-canvas :deep(.edgeLabel rect) { rx: 12; ry: 12; fill: #f5faff; stroke: #d9e7f2; }
.diagram-source { margin-top: 12px; font-size: 14px; }
.diagram-source pre { overflow: auto; max-height: 24rem; }
.diagram-source summary { cursor: pointer; }
.diagram-loading { color: var(--vp-c-text-2); }
@media print { .mermaid-canvas :deep(svg) { max-width: 100%; } }
</style>
