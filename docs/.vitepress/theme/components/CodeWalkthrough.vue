<script setup>
import { computed, ref, useId, watch } from 'vue'
import { VPButton } from 'vitepress/theme'
const props = defineProps({ encoded: { type: String, required: true } })
const data = computed(() => JSON.parse(decodeURIComponent(props.encoded)))
const selected = ref(-1)
watch(() => props.encoded, () => { selected.value = -1 })
const contentId = `code-steps-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const current = computed(() => data.value.steps[selected.value])
const html = computed(() => {
  const step = current.value
  if (!step) return data.value.html
  return data.value.html.replace(/class="([^"]*)" data-line="(\d+)"/g, (match, classes, line) => `class="${classes}${Number(line) >= step.from && Number(line) <= step.to ? ' ch-step-active' : ''}" data-line="${line}"`)
})
</script>
<template>
  <section class="code-walkthrough" aria-label="代码分步讲解">
    <div class="step-controls" aria-label="选择代码讲解步骤">
      <VPButton text="完整代码" :theme="selected === -1 ? 'brand' : 'alt'" :aria-pressed="selected === -1" :aria-controls="contentId" @click="selected = -1" />
      <VPButton v-for="(step, index) in data.steps" :key="index" :text="`步骤 ${index + 1}`" :theme="selected === index ? 'brand' : 'alt'" :aria-pressed="selected === index" :aria-controls="contentId" @click="selected = index" />
    </div>
    <p class="step-explanation" aria-live="polite">{{ current ? current.text : '先看完整代码，再按步骤查看对应行。复制按钮始终复制完整的干净源码。' }}</p>
    <div :class="`language-${data.lang} vp-adaptive-theme line-numbers-mode`">
      <button class="copy" title="复制完整代码" aria-label="复制完整代码"></button><span class="lang">{{ data.lang }}</span>
      <div :id="contentId" class="code-body" v-html="html"></div>
      <div class="line-numbers-wrapper" aria-hidden="true"><template v-for="n in data.lines" :key="n"><span class="line-number">{{ n }}</span><br></template></div>
    </div>
    <details><summary>展开全部步骤说明</summary><ol><li v-for="(step, index) in data.steps" :key="index">第 {{ step.from }}–{{ step.to }} 行：{{ step.text }}</li></ol></details>
  </section>
</template>
<style scoped>
.step-controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 24px; }
.step-explanation { min-height: 3.5em; }
.code-walkthrough { margin: 28px 0; }
.code-walkthrough details { font-size: 14px; margin-top: 12px; }
.code-walkthrough summary { cursor: pointer; }
.code-walkthrough :deep(.ch-step-active) { display: inline-block; width: 100%; background: var(--vp-code-line-highlight-color); box-shadow: inset 3px 0 var(--vp-c-brand-1); }
</style>
