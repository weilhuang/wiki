// Staging-only author check, using a supplied existing wiki installation.
import {readFileSync, writeFileSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {resolve, dirname, join} from 'node:path'
import {fileURLToPath, pathToFileURL} from 'node:url'
import {createRequire} from 'node:module'
import assert from 'node:assert/strict'
const wiki = resolve(process.argv[2])
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(join(wiki, 'package.json'))
const MarkdownIt = require('markdown-it'), matter = require('gray-matter')
const {JSDOM} = require('jsdom')
const {readTopics, validateTopic} = await import(pathToFileURL(join(wiki, 'scripts/knowledge.mjs')))
const {compileCode} = await import(pathToFileURL(join(wiki, 'scripts/render-codehike.mjs')))
const existing = readTopics(wiki)
const terms = JSON.parse(readFileSync(join(wiki, 'content/terms.json')))
const sources = JSON.parse(readFileSync(join(root, 'sources.json')))
const snippets = JSON.parse(readFileSync(join(root, 'snippets.json')))
const docs = [['module-boundaries.md','knowledge/architecture/boundaries/module-boundaries.md'],
              ['reliability-review.md','cases/orders/reliability-review.md']]
const ids = new Set([...existing.map(t=>t.id), 'architecture.module-boundaries','architecture.order-reliability-review'])
const urls = new Set([...existing.map(t=>t.url), ...docs.map(d=>'/'+d[1].replace('.md','.html')),
                      '/examples/architecture-review-lab.zip','/examples/architecture-review-results.json','/examples/architecture-review-regressions.json'])
const sourceIds = new Set(sources.map(s=>s.id))
const md = new MarkdownIt({html:true}), dom = new JSDOM('<!doctype html><html><body></body></html>')
globalThis.window = dom.window; globalThis.document = dom.window.document
const {default:mermaid} = await import(pathToFileURL(require.resolve('mermaid')))
mermaid.initialize({startOnLoad:false,securityLevel:'strict',htmlLabels:false})
const sha = s=>createHash('sha256').update(s).digest('hex')
const report = {revision:'A-r3-reconstructed',status:'pass',articles:[],diagrams:[],snippets:[],links:[],codeBlocks:0,
 limitations:['no full build','no browser/SSR/search','no framework runtime','new r3 checks do not prove lost r1 equivalence']}
for(const [name,source] of docs){
 const body=readFileSync(join(root,'articles',name),'utf8'), {data,content}=matter(body)
 validateTopic({...data,source},{terms}); assert.equal(data.status,'review'); assert.equal(data.reviewedAt,undefined)
 for(const relation of ['requires','recommendedBefore','related','contrastsWith'])
  for(const edge of data[relation])assert.ok(ids.has(edge.id),edge.id)
 for(const id of data.sourceRefs)assert.ok(sourceIds.has(id),id)
 const tokens=md.parse(content,{})
 assert.equal(tokens.filter(t=>t.type==='heading_open'&&t.tag==='h1').length,1)
 for(const block of tokens.filter(t=>t.type==='fence')){
  const [lang,...meta]=block.info.split(/\s+/)
  if(lang==='mermaid'){
   assert.match(block.content,/accTitle:/);assert.match(block.content,/accDescr:/)
   assert.doesNotMatch(block.content,/%%\{|classDef|<br|^\s*click\s/m)
   const result=await mermaid.parse(block.content)
   report.diagrams.push({article:name,type:result.diagramType,sha256:sha(block.content)})
  }else{await compileCode({value:block.content,lang,meta:meta.join(' ')});report.codeBlocks++}
 }
 for(const token of tokens.filter(t=>t.type==='inline'))for(const link of (token.children||[]).filter(t=>t.type==='link_open')){
  const href=link.attrGet('href');if(href.startsWith('/')){assert.ok(urls.has(href.split('#')[0]),href);report.links.push({article:name,href})}
 }
 report.articles.push({id:data.id,target:'docs/'+source,sha256:sha(body)})
}
for(const entry of snippets){
 const name=entry.doc.endsWith('module-boundaries.md')?docs[0][0]:docs[1][0]
 const body=readFileSync(join(root,'articles',name),'utf8'),marker=`<!-- snippet: ${entry.id} -->`
 assert.equal(body.split(marker).length,2)
 const block=md.parse(body.slice(body.indexOf(marker)+marker.length),{})[0]
 assert.equal(block.type,'fence')
 const {result}=await compileCode({value:block.content,lang:entry.language,meta:'steps'})
 const source=readFileSync(join(root,entry.source),'utf8')
 assert.equal(result.code.trimEnd(),source.trimEnd());assert.equal(sha(source),entry.sourceSha256)
 report.snippets.push({id:entry.id,sourceSha256:sha(source),steps:result.annotations.filter(a=>a.name==='step').length})
}
const integration=JSON.parse(readFileSync(join(root,'integration.json')))
for(const q of [...integration.reviewQuestions,...integration.searchIntents]){
 const name=q.topic==='architecture.module-boundaries'?docs[0][0]:docs[1][0]
 assert.ok(readFileSync(join(root,'articles',name),'utf8').includes(`{#${q.anchor}}`),q.anchor)
}
for(const edge of integration.futureRelationships){
 assert.ok(ids.has(edge.to),edge.to)
 const {data}=matter(readFileSync(join(root,'articles',docs[1][0]),'utf8'))
 assert.ok(!data.related.some(r=>r.id===edge.to),'future relationship activated too early')
}
dom.window.close()
writeFileSync(join(root,'records/author-static.json'),JSON.stringify(report,null,2)+'\n')
console.log(JSON.stringify({status:report.status,articles:report.articles.length,diagrams:report.diagrams.length,
 codeBlocks:report.codeBlocks,snippets:report.snippets.length,links:report.links.length}))
