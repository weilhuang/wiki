import { existsSync, readFileSync, readdirSync, lstatSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { createHash } from 'node:crypto'
import matter from 'gray-matter'
import MarkdownIt from 'markdown-it'
import { taxonomy, kinds, relationLabels } from '../content/taxonomy.mjs'
import { paths } from '../content/paths.mjs'
import { migrations } from '../content/migrations.mjs'
export { taxonomy, paths, kinds, relationLabels }
const markdown = new MarkdownIt({ html:true })
export const sourceUrl = source => `/${source.replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, '.html')}`
export const assert = (condition, message) => { if (!condition) throw new Error(message) }
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const strings = value => Array.isArray(value) && value.every(s=>typeof s==='string' && s.trim())
const safeSource = source => typeof source==='string' && /^[a-z0-9/-]+\.md$/.test(source) && !source.includes('..') && !source.startsWith('/')
const safeId = id => typeof id==='string' && /^[a-z][a-z0-9.-]*$/.test(id)
export const walk = dir => !existsSync(dir) ? [] : readdirSync(dir,{withFileTypes:true}).flatMap(e=>{
  assert(!e.isSymbolicLink(),`内容目录不接受符号链接: ${join(dir,e.name)}`)
  return e.isDirectory() ? (e.name.startsWith('.')?[]:walk(join(dir,e.name))) : e.name.endsWith('.md')?[join(dir,e.name)]:[]
})
function loadArrays(dir) {
  if(!existsSync(dir))return []
  return readdirSync(dir).filter(f=>f.endsWith('.json')).sort().flatMap(file=>{
    const path=join(dir,file);assert(lstatSync(path).isFile()&&!lstatSync(path).isSymbolicLink(),`非法台账文件 ${path}`)
    const data=JSON.parse(readFileSync(path,'utf8'));assert(Array.isArray(data),`台账必须为数组 ${path}`);return data
  })
}
export function registries(root=process.cwd()) {
  const out={sources:loadArrays(join(root,'content/sources')),verification:loadArrays(join(root,'content/verification')),terms:JSON.parse(readFileSync(join(root,'content/terms.json'),'utf8'))}
  for(const kind of ['sources','verification']) {const ids=new Set();for(const item of out[kind]){assert(typeof item.id==='string'&&/^[a-z][A-Za-z0-9.-]*$/.test(item.id)&&!ids.has(item.id),`重复或非法 ${kind} ID: ${item.id}`);ids.add(item.id)}}
  for(const s of out.sources){assert(typeof s.title==='string'&&s.title.trim()&&/^https:\/\//.test(s.url),`${s.id}: 来源需要标题与 HTTPS URL`);assert(['specification','api','source','documentation','paper'].includes(s.type),`${s.id}: 非法来源类型`)}
  return out
}
export function validateTopic(topic,{domains=taxonomy,terms}={}) {
  for(const key of ['id','title','description','domain','category','scope','date']) assert(typeof topic[key]==='string'&&topic[key].trim(),`${topic.source}: ${key} 必须为非空字符串`)
  assert(safeId(topic.id),`非法知识 ID: ${topic.id}`)
  assert(Object.hasOwn(kinds,topic.kind),`${topic.id}: 非法文章类型`)
  assert(['planned','draft','review','published','retired'].includes(topic.status),`${topic.id}: 非法编辑状态`)
  assert(safeSource(topic.source),`${topic.id}: 非法 canonical source`)
  const domain=domains.find(d=>d.id===topic.domain);assert(domain,`${topic.id}: 未知领域 ${topic.domain}`)
  assert(domain.categories.some(c=>c.id===topic.category),`${topic.id}: 未知分类 ${topic.category}`)
  for(const key of ['date','updated','reviewedAt']) if(topic[key]!=null)assert(/^\d{4}-\d{2}-\d{2}$/.test(topic[key])&&!Number.isNaN(Date.parse(topic[key]))&&new Date(topic[key]).toISOString().slice(0,10)===topic[key],`${topic.id}: 无效 ${key}`)
  for(const key of ['prerequisites','searchTerms','sourceRefs','verificationRefs','versions','objectives'])if(topic[key]!==undefined)assert(strings(topic[key]),`${topic.id}: ${key} 必须为字符串数组`)
  assert(topic.tags&&typeof topic.tags==='object'&&!Array.isArray(topic.tags),`${topic.id}: tags 必须按维度分组`)
  for(const[dimension,ids]of Object.entries(topic.tags)){assert(['technology','mechanism','task','scenario'].includes(dimension)&&strings(ids),`${topic.id}: 非法标签维度`);if(terms)for(const id of ids)assert(Object.hasOwn(terms[dimension]||{},id),`${topic.id}: 未登记标签 ${dimension}/${id}`)}
  for(const relation of Object.keys(relationLabels))if(topic[relation]!==undefined){assert(Array.isArray(topic[relation]),`${topic.id}: 非法关系 ${relation}`);assert(new Set(topic[relation].map(edge=>edge.id)).size===topic[relation].length,`${topic.id}: 重复关系 ${relation}`);for(const edge of topic[relation])assert(safeId(edge.id)&&typeof edge.reason==='string'&&edge.reason.trim(),`${topic.id}: ${relation} 缺少明确目标或原因`)}
  assert(!Object.hasOwn(topic,'pathId')&&!Object.hasOwn(topic,'order'),`${topic.id}: 知识页不能由唯一路线或章节序号持有`)
  return true
}
export function validateStructure(topics, {domains=taxonomy,routes=paths,terms,planned=[]}={}) {
  const ids=new Set(),urls=new Set(),domainIds=new Set()
  for(const domain of domains){assert(/^[a-z][a-z0-9-]*$/.test(domain.id)&&domain.categories.every(c=>/^[a-z][a-z0-9-]*$/.test(c.id)),`非法领域/分类ID ${domain.id}`);assert(!domainIds.has(domain.id),`重复领域 ${domain.id}`);domainIds.add(domain.id);assert(new Set(domain.categories.map(c=>c.id)).size===domain.categories.length,`${domain.id}: 重复分类`)}
  for(const topic of topics){validateTopic(topic,{domains,terms});assert(!ids.has(topic.id),`重复知识 ID: ${topic.id}`);ids.add(topic.id);const url=sourceUrl(topic.source);assert(!urls.has(url),`重复 canonical route: ${url}`);urls.add(url)}
  const plannedIds=new Set(planned.map(p=>p.id))
  for(const topic of topics)for(const relation of Object.keys(relationLabels))for(const edge of topic[relation]||[]){assert(ids.has(edge.id)||plannedIds.has(edge.id),`${topic.id}: 未知关系目标 ${edge.id}`);assert(edge.id!==topic.id,`${topic.id}: 关系不能指向自己`)}
  const done=new Set(),active=new Set(),byId=new Map(topics.map(t=>[t.id,t]))
  const visit=id=>{if(done.has(id)||plannedIds.has(id))return;assert(!active.has(id),`强先修关系存在环: ${id}`);active.add(id);for(const e of byId.get(id).requires||[])visit(e.id);active.delete(id);done.add(id)}
  for(const id of ids)visit(id)
  const routeIds=new Set(),routeSources=new Set()
  for(const route of routes){assert(!routeIds.has(route.id)&&safeId(route.id),`重复或非法路线 ID: ${route.id}`);routeIds.add(route.id);assert(!routeSources.has(route.source),`重复路线 source: ${route.source}`);routeSources.add(route.source);assert(!urls.has(sourceUrl(route.source)),`路线覆盖知识正文: ${route.source}`);assert(['planned','draft','review','published','retired'].includes(route.status),`${route.id}: 非法路线状态`);assert(safeSource(route.source)&&strings(route.entry)&&route.entry.length&&route.goal,`${route.id}: 路线缺少准入/目标`);const readings=route.stages.flatMap(s=>{assert(s.title&&s.task&&Array.isArray(s.readings),`${route.id}: 阶段缺少增量任务`);return s.readings});assert(readings.length,`${route.id}: 空路线`);for(const r of readings){assert(['required','optional'].includes(r.role)&&r.purpose,`${route.id}: 阅读缺少角色/目的`);assert(ids.has(r.topic)||plannedIds.has(r.topic),`${route.id}: 未知路线主题 ${r.topic}`);if(route.status==='published')assert(byId.get(r.topic)?.status==='published',`${route.id}: 已发布路线引用未完成主题 ${r.topic}`)}}
  return true
}
export function readTopics(root=process.cwd(),{strict=false}={}) {
  const {terms}=registries(root),out=[]
  for(const file of walk(join(root,'docs'))){const {data,content}=matter(readFileSync(file,'utf8'));if(data.status&&data.status!=='published')throw Error(`${relative(root,file)}: 非 published 正文不能进入公开 docs`);if(!data.id){const relativeSource=relative(join(root,'docs'),file).replaceAll('\\','/');assert(!/^(knowledge|cases|troubleshooting)\//.test(relativeSource)||relativeSource.endsWith('/index.md'),`${relativeSource}: 知识正文缺少稳定 ID`);continue}
    const source=relative(join(root,'docs'),file).replaceAll('\\','/')
    const topic={...data,source,url:sourceUrl(source)};validateTopic(topic,{terms});assert(topic.status==='published',`${source}: 草稿必须放在 docs 之外`)
    assert(markdown.parse(content,{}).filter(t=>t.type==='heading_open'&&t.tag==='h1').length===1,`${source}: 正文需要恰好一个 H1`)
    assert(content.replace(/```[\s\S]*?```/g,'').trim().length>120,`${source}: 不发布空知识页`)
    const plain=content.replace(/```[\s\S]*?```/g,'').replace(/<[^>]*>/g,'');topic.minutes=Math.max(1,Math.ceil((plain.match(/[\u3400-\u9fff]/g)||[]).length/450+(plain.match(/[A-Za-z0-9_]+/g)||[]).length/220))
    topic.tagLabels=Object.entries(topic.tags).flatMap(([dim,ids])=>ids.map(id=>terms[dim][id]));topic.domainTitle=taxonomy.find(d=>d.id===topic.domain).title;topic.categoryTitle=taxonomy.find(d=>d.id===topic.domain).categories.find(c=>c.id===topic.category).title;topic.kindTitle=kinds[topic.kind];out.push(topic)
  }
  out.sort((a,b)=>taxonomy.findIndex(d=>d.id===a.domain)-taxonomy.findIndex(d=>d.id===b.domain)||a.category.localeCompare(b.category)||a.id.localeCompare(b.id))
  validateStructure(out,{terms,routes:strict?paths:paths.filter(p=>p.stages.flatMap(s=>s.readings).every(r=>out.some(t=>t.id===r.topic)))})
  return out
}
export function aliasEntries(root=process.cwd()) {return JSON.parse(readFileSync(join(root,'content/redirects.json'),'utf8'))}
export function validateAliases(aliases,topics,otherSources=[]) {
  const canonical=new Set([...topics.map(t=>t.url||sourceUrl(t.source)),...otherSources.map(sourceUrl)]),seen=new Set()
  for(const a of aliases){assert(/^\/[a-z0-9/-]+(?:\.html)?$/.test(a.from)&&!a.from.includes('..'),`非法 alias ${a.from}`);assert(!seen.has(a.from)&&!canonical.has(a.from),`重复 alias ${a.from}`);seen.add(a.from);assert(canonical.has(a.to),`alias 未直达 canonical: ${a.from} → ${a.to}`);for(const target of Object.values(a.anchors||{}))assert(typeof target==='string'&&canonical.has(target.split('#')[0]),`${a.from}: 非法锚点映射`)}
  return true
}
export function generatedSources(topics,{domains=taxonomy,routes=paths}={}) {
  return ['index.md','knowledge/index.md','paths/index.md','cases/index.md','resources/source-reading.md','resources/experiments.md','resources/review.md','tags.md','guide/knowledge-map.md','guide/practice.md','guide/roadmap.md','about.md',...routes.map(p=>p.source),...domains.flatMap(d=>[`knowledge/${d.id}/index.md`,...d.categories.filter(c=>topics.some(t=>t.domain===d.id&&t.category===c.id)).map(c=>`knowledge/${d.id}/${c.id}/index.md`)])]
}
export function validateOutputRoutes(topics,{domains=taxonomy,routes=paths,aliases=aliasEntries()}={}) {
  validateStructure(topics,{domains,routes})
  const planned=generatedSources(topics,{domains,routes}),seen=new Set(topics.map(t=>sourceUrl(t.source)))
  for(const source of planned){const route=sourceUrl(source);assert(!seen.has(route),`生成页面路由冲突: ${source}`);seen.add(route)}
  validateAliases(aliases,topics,planned)
  return true
}
export function topicNavigation() { return {prev:false,next:false} }
function validateLegacyEvidence(root,record,topic) {
  assert(/^evidence\/[a-z0-9-]+\.json$/.test(record.legacyEvidence),'非法历史证据路径')
  const e=JSON.parse(readFileSync(join(root,record.legacyEvidence),'utf8'))
  assert(e.chapterIds?.includes(topic.legacyId),`${topic.id}: 历史运行不覆盖本知识页`)
  assert(e.status==='verified'&&(!e.reviewStatus||e.reviewStatus==='approved')&&strings(e.scope)&&Array.isArray(e.notCovered),`${record.id}: 历史运行没有通过或缺少范围`)
  assert(e.commands?.length&&e.commands.every(c=>c.command&&c.exitCode===0)&&e.versions?.length,`${record.id}: 缺少真实命令与版本`)
  for(const artifact of e.artifacts||[]){assert(/^examples\/[a-z0-9-]+\.zip$/.test(artifact.path),`${record.id}: 非法下载路径`);assert(hash(readFileSync(join(root,'docs/public',artifact.path)))===artifact.sha256,`${record.id}: 冻结实验 ZIP 已变化`)}
  if(e.verification){const bytes=readFileSync(join(root,'docs/public',e.verification.path));assert(hash(bytes)===e.verification.sha256,`${record.id}: 公开运行摘要已变化`);const summary=JSON.parse(bytes);assert(summary.status==='verified'&&summary.independentlyReviewed&&summary.sourceSnapshot.sourceManifestSha256===e.sourceManifestSha256,`${record.id}: 摘要没有绑定已复核源码`)}
  return e
}
export function validateEvidence(root,topics,registry=registries(root)) {
  for(const topic of topics){for(const id of topic.sourceRefs||[])assert(registry.sources.some(s=>s.id===id),`${topic.id}: 缺失来源 ${id}`)
    for(const id of topic.verificationRefs||[]){const e=registry.verification.find(r=>r.id===id);assert(e,`${topic.id}: 缺失验证记录 ${id}`);assert(['source-reviewed','static-checked','executed'].includes(e.kind)&&['not-run','pass','fail','blocked','stale'].includes(e.status),`${id}: 非法证据类型/状态`)
      if(e.legacyEvidence){validateLegacyEvidence(root,e,topic);continue}
      assert(Array.isArray(e.scope)&&e.scope.length&&Array.isArray(e.limitations),`${id}: 证据缺少范围/限制`)
      if(e.status==='pass'&&e.kind==='executed'){assert(e.sourceFiles?.length&&e.commands?.length&&e.commands.every(c=>c.command&&Number.isInteger(c.exitCode)&&(c.exitCode===0||(c.expectation==='expected-rejection'&&c.exitCode===c.expectedExitCode&&c.expectedExitCode>0))),`${id}: executed/pass 必须绑定源码与成功命令`)}
      for(const snapshot of e.upstreamSnapshots||[])assert(/^https:\/\//.test(snapshot.url)&&snapshot.tag&&/^[a-f0-9]{64}$/.test(snapshot.sha256),`${id}: 上游源码快照需要固定版本、URL与SHA256`)
      for(const file of [...(e.sourceFiles||[]),...(e.artifacts||[])]){assert(typeof file.path==='string'&&!file.path.startsWith('/')&&!file.path.split('/').includes('..')&&/^[a-f0-9]{64}$/.test(file.sha256),`${id}: 非法证据文件身份`);const path=resolve(root,file.path);let ancestor=resolve(root);for(const segment of file.path.split('/')){ancestor=join(ancestor,segment);assert(existsSync(ancestor)&&!lstatSync(ancestor).isSymbolicLink(),`${id}: 证据路径不能穿过符号链接 ${file.path}`)}assert(path.startsWith(resolve(root)+'/')&&existsSync(path)&&lstatSync(path).isFile()&&!lstatSync(path).isSymbolicLink(),`${id}: 缺少普通证据文件 ${file.path}`);assert(hash(readFileSync(path))===file.sha256,`${id}: 源码/制品变化，旧证据 stale: ${file.path}`)}
    }
    if(topic.kind==='lab')assert(topic.verificationRefs?.length,`${topic.id}: 实验教程必须明确验证记录，未运行也应标明`)
  }
  return true
}
export function validateReadiness(root=process.cwd(),{requireNewBatch=true}={}) {
  const topics=readTopics(root,{strict:true}),registry=registries(root);validateEvidence(root,topics,registry)
  for(const record of registry.verification)if(record.publicPackaging)assert(record.publicPackaging.reviewStatus==='approved',`${record.id}: public packaging 未经独立复核`)
  const sources=walk(join(root,'docs')).map(f=>relative(join(root,'docs'),f).replaceAll('\\','/'));validateAliases(aliasEntries(root),topics,sources.filter(s=>!topics.some(t=>t.source===s)))
  for(const old of migrations)assert(topics.some(t=>t.id===old.id),`旧知识迁移缺失: ${old.id}`)
  for(const domain of taxonomy)assert(sources.includes(`knowledge/${domain.id}/index.md`),`缺少领域导读 ${domain.id}`)
  for(const route of paths)assert(sources.includes(route.source),`缺少路线导读 ${route.id}`)
  for(const source of ['index.md','knowledge/index.md','paths/index.md','cases/index.md','resources/source-reading.md','resources/experiments.md','resources/review.md','about.md'])assert(sources.includes(source),`缺少知识入口 ${source}`)
  if(requireNewBatch)for(const id of ['java.hashmap','frameworks.bean-definition-registration','architecture.order-service-extraction'])assert(topics.some(t=>t.id===id&&t.status==='published'),`本次内容样板尚未完成: ${id}`)
  return topics
}
