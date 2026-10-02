<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { withBase } from 'vitepress'
import { data } from '../../topics.data.mjs'
const props=defineProps({mode:{type:String,default:'topics'}})
const selected=ref({domain:'',kind:'',task:''})
const visible=computed(()=>data.topics.filter(t=>(!selected.value.domain||t.domain===selected.value.domain)&&(!selected.value.kind||t.kind===selected.value.kind)&&(props.mode==='review'||!selected.value.task||t.tags.task?.includes(selected.value.task))))
const questions=computed(()=>data.questions.filter(q=>visible.value.some(t=>t.id===q.topic)&&(!selected.value.task||q.task===selected.value.task)))
const topicById=id=>data.topics.find(t=>t.id===id)
function readQuery(){const query=new URLSearchParams(window.location.search);selected.value={domain:data.domains.some(d=>d.id===query.get('domain'))?query.get('domain'):'',kind:Object.hasOwn(data.kinds,query.get('kind'))?query.get('kind'):'',task:Object.hasOwn(data.terms.task,query.get('task'))?query.get('task'):''}}
function change(){const url=new URL(window.location.href);for(const key of ['domain','kind','task']){if(selected.value[key])url.searchParams.set(key,selected.value[key]);else url.searchParams.delete(key)}window.history.pushState(window.history.state,'',url.pathname+url.search+url.hash)}
function reset(){selected.value={domain:'',kind:'',task:''};change()}
onMounted(()=>{readQuery();window.addEventListener('popstate',readQuery)})
onUnmounted(()=>window.removeEventListener('popstate',readQuery))
</script>
<template>
  <section aria-label="组合筛选知识" class="topic-list">
    <noscript><p>筛选需要 JavaScript；下面仍可阅读完整知识列表和推理问题</p></noscript>
    <div class="facets">
      <label>领域 <select v-model="selected.domain" @change="change"><option value="">全部领域</option><option v-for="d in data.domains" :key="d.id" :value="d.id">{{ d.title }}</option></select></label>
      <label>文章类型 <select v-model="selected.kind" @change="change"><option value="">全部类型</option><option v-for="(label,id) in data.kinds" :key="id" :value="id">{{ label }}</option></select></label>
      <label>能力任务 <select v-model="selected.task" @change="change"><option value="">全部任务</option><option v-for="(label,id) in data.terms.task" :key="id" :value="id">{{ label }}</option></select></label>
      <button type="button" @click="reset">重置筛选</button>
    </div>
    <p aria-live="polite">{{ mode==='review'?questions.length:visible.length }} {{ mode==='review'?'个推理问题':'篇知识文章' }}</p>
    <template v-if="mode==='review'">
      <article v-for="q in questions" :key="q.id">
        <h2>{{ q.prompt }}</h2><p>{{ topicById(q.topic).domainTitle }} · {{ topicById(q.topic).kindTitle }} · {{ data.terms.task[q.task] }}</p>
        <details><summary>查看推理依据</summary><p>先列出对象、状态和条件，再对照 <a :href="withBase(topicById(q.topic).url+'#'+q.anchor)">{{ topicById(q.topic).title }}的相应解释</a>，检查你的预测在哪一项条件下成立</p></details>
      </article>
    </template>
    <template v-else><article v-for="topic in visible" :key="topic.id"><h2><a :href="withBase(topic.url)">{{ topic.title }}</a></h2><p>{{ topic.domainTitle }} / {{ topic.categoryTitle }} · {{ topic.kindTitle }} · 约 {{ topic.minutes }} 分钟</p><p>{{ topic.description }}</p><p class="tags">{{ topic.tagLabels.join(' · ') }}</p></article></template>
    <p v-if="mode==='review'?!questions.length:!visible.length">这个组合还没有可读内容，可以移除一个条件；规划主题不作为搜索或筛选结果</p>
  </section>
</template>
<style scoped>
.facets { display:flex; flex-wrap:wrap; align-items:end; gap:12px; margin:24px 0; }
label { display:flex; flex-direction:column; gap:4px; font-size:14px; }
select, button { border:1px solid var(--vp-c-divider); border-radius:6px; padding:6px 10px; background:var(--vp-c-bg); color:var(--vp-c-text-1); font:inherit; }
select { max-width:100%; }
button { cursor:pointer; }
select:focus-visible,button:focus-visible,summary:focus-visible { outline:2px solid var(--vp-c-brand-1); outline-offset:3px; }
article { margin:30px 0; }
.tags { color:var(--vp-c-text-2); font-size:14px; }
@media(max-width:600px){ label { width:100%; } }
</style>
