import { taxonomy, paths, kinds, relationLabels, sourceUrl } from './knowledge.mjs'
const link=t=>`[${t.title}](${t.url})`
export function topicContextMarkdown(topic,topics) {
  const domain=taxonomy.find(d=>d.id===topic.domain), category=domain.categories.find(c=>c.id===topic.category)
  const breadcrumb=`[知识目录](/knowledge/) / [${domain.title}](/knowledge/${domain.id}/) / [${category.title}](/knowledge/${domain.id}/${category.id}/) · ${kinds[topic.kind]}\n\n`
  const requirements=(topic.requires||[]).map(r=>{const target=topics.find(t=>t.id===r.id);return `${target?link(target):r.id}：${r.reason}`})
  const prerequisite=[...(topic.prerequisites||[]),...requirements]
  let bottom='\n\n## 相关知识与路线 {#knowledge-connections}\n\n'
  for(const relation of Object.keys(relationLabels).filter(r=>r!=='requires')){
    const edges=topic[relation]||[];if(!edges.length)continue
    bottom+=`**${relationLabels[relation]}**\n\n`+edges.map(e=>{const target=topics.find(t=>t.id===e.id);return `- ${target?link(target):e.id}：${e.reason}`}).join('\n')+'\n\n'
  }
  for(const path of paths){const readings=path.stages.flatMap(s=>s.readings),index=readings.findIndex(r=>r.topic===topic.id);if(index<0)continue
    bottom+=`**所在路线：[${path.title}](${sourceUrl(path.source)})**。本节点的任务：${readings[index].purpose}。\n\n`
    const prev=topics.find(t=>t.id===readings[index-1]?.topic),next=topics.find(t=>t.id===readings[index+1]?.topic)
    if(prev||next)bottom+=`路线建议顺序（不是强先修）：${prev?'前一项 '+link(prev):'本路线起点'}；${next?'后一项 '+link(next):'本路线收束'}。\n\n`
  }
  bottom+='按其他任务继续：[源码阅读](/resources/source-reading.html) · [实验与验证](/resources/experiments.html) · [复习与推理](/resources/review.html)\n'
  const scope=`**适用范围：**${topic.scope}\n\n`+(prerequisite.length?`**理解先修：**${prerequisite.join('；')}。\n\n`:'')
  return {breadcrumb,scope,bottom}
}
export function addTopicContext(md,topics) {
  md.core.ruler.before('normalize','wiki-topic-context',state=>{
    if(state.env.wikiSearch)return
    const topic=topics.find(t=>t.source===state.env.relativePath);if(!topic)return
    const {breadcrumb,scope,bottom}=topicContextMarkdown(topic,topics)
    // Keep the author's concrete opening problem ahead of catalog metadata.
    state.src=state.src.replace(/^(# .+\n)/m,`$1\n${breadcrumb}`).replace(/^(## .+\n)/m,`${scope}$1`)+bottom
  })
}
