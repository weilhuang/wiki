import { existsSync, readFileSync, readdirSync, lstatSync } from 'node:fs'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import matter from 'gray-matter'
import MarkdownIt from 'markdown-it'
import { curriculum } from '../curriculum.mjs'
export { curriculum }
const markdown = new MarkdownIt({ html:true })
const headingCount = content => markdown.parse(content, {}).filter(token=>token.type==='heading_open' && token.tag==='h1').length
export const sourceUrl = source => `/${source.replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, '.html')}`
const walk = dir => !existsSync(dir) ? [] : readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(join(dir, e.name)) : e.name.endsWith('.md') ? [join(dir, e.name)] : [])
const safeSource = source => typeof source === 'string' && /^[a-z0-9/-]+\.md$/.test(source) && !source.includes('..') && !source.startsWith('/')
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const strings = value => Array.isArray(value) && value.length > 0 && value.every(s => typeof s === 'string' && s.trim())
export function validateStructure(model = curriculum) {
  const pathIds = new Set(), ids = new Set(), routes = new Set(), themes = new Set(model.themes.map(t => t.id))
  assert(model.paths.length === model.batch.expectedPaths, '课程路径数量与批次合同不符')
  for (const path of model.paths) {
    assert(!pathIds.has(path.id), `重复路径 ID: ${path.id}`); pathIds.add(path.id)
    assert(themes.has(path.themeId), `${path.id}: 未知主题`)
    assert(safeSource(path.introSource), `${path.id}: 非法导读 source`)
    assert(strings(path.prerequisites) && strings(path.outcomes), `${path.id}: 缺少先修或成果`)
  }
  for (const chapter of model.chapters) {
    assert(!ids.has(chapter.id), `重复章节 ID: ${chapter.id}`); ids.add(chapter.id)
    assert(pathIds.has(chapter.pathId), `${chapter.id}: 未知路径`)
    assert(safeSource(chapter.source) && chapter.source.startsWith(`learn/${chapter.pathId}/`), `${chapter.id}: 非法章节 source`)
    const url = sourceUrl(chapter.source); assert(!routes.has(url), `重复章节 route: ${url}`); routes.add(url)
    assert(['draft', 'ready'].includes(chapter.contentStatus), `${chapter.id}: 非法内容状态`)
  }
  for (const path of model.paths) {
    const chapters = model.chapters.filter(c => c.pathId === path.id).sort((a,b) => a.order-b.order)
    assert(chapters.length === model.batch.chaptersPerPath, `${path.id}: 章节数量与批次合同不符`)
    assert(chapters.every((c,i) => c.order === i+1), `${path.id}: 章节顺序必须连续且唯一`)
    const stages = path.stages.flatMap(s => s.chapters)
    assert(JSON.stringify(stages) === JSON.stringify(chapters.map(c=>c.id)), `${path.id}: 阶段与章节顺序不一致`)
  }
  const visited = new Set(), active = new Set()
  const visit = id => {
    assert(ids.has(id), `未知先修章节: ${id}`); assert(!active.has(id), `先修关系存在环: ${id}`)
    if (visited.has(id)) return
    active.add(id)
    for (const prerequisite of model.chapters.find(c=>c.id===id).prerequisites) visit(prerequisite)
    active.delete(id); visited.add(id)
  }
  for (const id of ids) visit(id)
  const aliases = aliasEntries(model)
  const aliasIds = new Set()
  for (const alias of aliases) {
    assert(/^\/[a-z0-9/-]+(?:\.html)?$/.test(alias.from) && !alias.from.includes('..'), `非法 alias: ${alias.from}`)
    assert(!aliasIds.has(alias.from) && !routes.has(alias.from), `重复 alias: ${alias.from}`); aliasIds.add(alias.from)
    assert(routes.has(alias.to) || model.paths.some(p=>sourceUrl(p.introSource)===alias.to) || alias.to === '/learn/', `alias 目标未登记: ${alias.to}`)
  }
  return true
}
export function aliasEntries(model = curriculum) {
  return [...model.aliases, ...model.chapters.flatMap(c => c.aliases.map(from => ({ from, to: sourceUrl(c.source) })))]
}
export function readChapters(root = process.cwd(), { model = curriculum, strict = false } = {}) {
  validateStructure(model)
  const out = [], missing = []
  for (const chapter of model.chapters) {
    const file = join(root, 'docs', chapter.source)
    if (!existsSync(file)) { missing.push(chapter.source); continue }
    assert(chapter.contentStatus === 'ready', `${chapter.source}: draft 必须放在 docs 之外`)
    assert(lstatSync(file).isFile() && !lstatSync(file).isSymbolicLink(), `${chapter.source}: 章节必须是普通文件`)
    const { data, content } = matter(readFileSync(file, 'utf8'))
    assert(!data.draft && data.contentStatus !== 'draft', `${chapter.source}: 草稿不能进入公开目录`)
    for (const key of ['title', 'description', 'date']) assert(typeof data[key] === 'string' && data[key].trim(), `${chapter.source}: ${key} 必须为非空字符串`)
    for (const key of ['date', 'updated']) if (data[key]) assert(/^\d{4}-\d{2}-\d{2}$/.test(data[key]) && new Date(`${data[key]}T00:00:00Z`).toISOString().slice(0,10)===data[key], `${chapter.source}: ${key} 日期无效`)
    for (const key of ['tags', 'objectives', 'versions']) assert(strings(data[key]), `${chapter.source}: ${key} 必须为非空字符串数组`)
    assert(headingCount(content)===1, `${chapter.source}: 正文需要恰好一个一级标题`)
    const plain = content.replace(/```[\s\S]*?```/g, '').replace(/<[^>]*>/g, '')
    const minutes = Math.max(1, Math.ceil((plain.match(/[\u3400-\u9fff]/g)||[]).length/450 + (plain.match(/[A-Za-z0-9_]+/g)||[]).length/220))
    const path = model.paths.find(p=>p.id===chapter.pathId)
    out.push({ ...chapter, ...Object.fromEntries(['title','description','date','updated','tags','objectives','versions'].filter(k=>data[k]!==undefined).map(k=>[k,data[k]])), tags:[...new Set(data.tags)], category:path.title, pathTitle:path.title, minutes, url:sourceUrl(chapter.source) })
  }
  const registered = new Set([...model.chapters.map(c=>join(root,'docs',c.source)), ...model.paths.map(p=>join(root,'docs',p.introSource)), join(root,'docs/learn/index.md')])
  for (const file of walk(join(root,'docs/learn'))) assert(registered.has(file), `未登记学习页面: ${file.slice(root.length+1)}`)
  if (strict) assert(!missing.length, `首批课程尚未齐备，缺少 ${missing.length} 章：\n${missing.join('\n')}`)
  return out
}
export function chapterNavigation(chapter, chapters) {
  const siblings = chapters.filter(c=>c.pathId===chapter.pathId).sort((a,b)=>a.order-b.order)
  const index = siblings.findIndex(c=>c.id===chapter.id)
  const link = c => c ? { text:c.title, link:c.url } : false
  return { prev:link(siblings[index-1]), next:link(siblings[index+1]) }
}
export function validateReadiness(root = process.cwd(), model = curriculum) {
  const chapters = readChapters(root, { model, strict:true })
  for (const source of [...model.requiredPages, ...model.paths.map(p=>p.introSource)]) {
    const file=join(root,'docs',source)
    assert(existsSync(file), `缺少完整导读/指南: ${source}`)
    assert(lstatSync(file).isFile() && !lstatSync(file).isSymbolicLink(), `${source}: 指南必须是普通文件`)
    const { data, content }=matter(readFileSync(file,'utf8'))
    assert(!data.draft && typeof data.title==='string' && typeof data.description==='string' && headingCount(content)===1, `${source}: 指南缺少标题/摘要或含草稿状态`)
  }
  const checked = new Map()
  for (const chapter of chapters) {
    assert(chapter.evidence && /^evidence\/[a-z0-9-]+\.json$/.test(chapter.evidence), `${chapter.id}: 缺少有效证据引用`)
    const path = join(root,chapter.evidence)
    assert(existsSync(path), `${chapter.id}: 缺少执行证据 ${chapter.evidence}`)
    const e = checked.get(chapter.evidence) || JSON.parse(readFileSync(path,'utf8'))
    assert(e.chapterIds?.includes(chapter.id), `${chapter.id}: 执行证据不覆盖本章`)
    assert(e.status==='verified' && (!e.reviewStatus || e.reviewStatus==='approved') && strings(e.scope) && Array.isArray(e.notCovered), `${chapter.evidence}: 基础实验尚未 verified 或范围未说明`)
    assert(strings(e.versions) && e.commands?.length && e.commands.every(c=>typeof c.command==='string' && c.command && c.exitCode===0), `${chapter.evidence}: 缺少成功执行命令与精确版本`)
    assert(e.artifacts?.length, `${chapter.evidence}: 缺少源码 artifact`)
    for (const artifact of e.artifacts) {
      assert(/^examples\/[a-z0-9-]+\.zip$/.test(artifact.path) && /^[a-f0-9]{64}$/.test(artifact.sha256), `${chapter.evidence}: 非法 artifact`)
      const artifactPath=join(root,'docs/public',artifact.path)
      assert(existsSync(artifactPath), `缺少实验下载 ${artifact.path}`)
      assert(createHash('sha256').update(readFileSync(artifactPath)).digest('hex')===artifact.sha256, `实验文件与执行证据不一致: ${artifact.path}`)
    }
    if (e.verification) {
      assert(/^examples\/[a-z0-9-]+\.json$/.test(e.verification.path) && /^[a-f0-9]{64}$/.test(e.verification.sha256), `${chapter.evidence}: 非法公开验证摘要`)
      const bytes=readFileSync(join(root,'docs/public',e.verification.path))
      assert(createHash('sha256').update(bytes).digest('hex')===e.verification.sha256, `${chapter.evidence}: 公开验证摘要哈希不一致`)
      const summary=JSON.parse(bytes)
      assert(summary.status==='verified' && summary.independentlyReviewed===true && summary.sourceSnapshot.sourceManifestSha256===e.sourceManifestSha256, `${chapter.evidence}: 验证摘要没有绑定已复核源码`)
    }
    assert(e.artifacts.some(a=>`/${a.path}`===chapter.practice), `${chapter.id}: 实验下载没有执行证据`)
    checked.set(chapter.evidence,e)
  }
  return chapters
}
