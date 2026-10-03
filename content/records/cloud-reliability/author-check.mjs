// Read-only package check. Reuses the explicitly supplied existing wiki install.
import {readFileSync, writeFileSync, existsSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {resolve, dirname, join} from 'node:path'
import {fileURLToPath, pathToFileURL} from 'node:url'
import {createRequire} from 'node:module'
import assert from 'node:assert/strict'

const wiki = resolve(process.argv[2])
const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(join(wiki, 'package.json'))
const MarkdownIt = require('markdown-it')
const matter = require('gray-matter')
const {JSDOM} = require('jsdom')
const yaml = require('js-yaml')
const {readTopics, validateTopic} = await import(pathToFileURL(join(wiki, 'scripts/knowledge.mjs')))
const {compileCode} = await import(pathToFileURL(join(wiki, 'scripts/render-codehike.mjs')))
const existing = readTopics(wiki)
const terms = JSON.parse(readFileSync(join(wiki, 'content/terms.json')))
Object.assign(terms.technology, {kubernetes: 'Kubernetes'})
Object.assign(terms.mechanism, {observability: '可观测性', slo: '服务目标'})
const md = new MarkdownIt()
const dom = new JSDOM('<!doctype html><html><body></body></html>')
globalThis.window = dom.window
globalThis.document = dom.window.document
const {default: mermaid} = await import(pathToFileURL(require.resolve('mermaid')))
mermaid.initialize({startOnLoad: false, securityLevel: 'strict', htmlLabels: false})
const hash = data => createHash('sha256').update(data).digest('hex')
const articles = [
  ['service-level-signals.md', 'knowledge/cloud/observability/service-level-signals.md'],
  ['readiness-draining.md', 'knowledge/cloud/lifecycle/readiness-draining.md']
]
const ids = new Set([...existing.map(t=>t.id), 'cloud.service-level-signals', 'cloud.readiness-draining'])
const sources = JSON.parse(readFileSync(join(packageRoot, 'sources.json')))
const sourceIds = new Set(sources.map(s=>s.id))
const snippets = JSON.parse(readFileSync(join(packageRoot, 'snippets.json')))
const report = {status: 'pass', articles: [], diagrams: [], snippets: [], yaml: null,
  limitation: 'Parsing and snippet checks only; no browser, SSR or Kubernetes API validation'}
let ordinaryBlocks = 0
for (const [name, source] of articles) {
  const text = readFileSync(join(packageRoot, 'articles', name), 'utf8')
  const {data, content} = matter(text)
  validateTopic({...data, source}, {terms})
  assert.equal(data.status, 'review')
  assert.equal(data.reviewedAt, undefined)
  for (const type of ['requires','recommendedBefore','related','contrastsWith'])
    for (const edge of data[type] || []) assert.ok(ids.has(edge.id), edge.id)
  for (const id of data.sourceRefs) assert.ok(sourceIds.has(id), id)
  const tokens = md.parse(content, {})
  assert.equal(tokens.filter(t=>t.type==='heading_open' && t.tag==='h1').length, 1)
  assert.ok(!text.includes('/workspace/') && !text.includes('/tmp/'))
  for (const token of tokens.filter(t=>t.type==='fence')) {
    const [lang, ...meta] = token.info.split(/\s+/)
    if (lang === 'mermaid') {
      assert.match(token.content, /accTitle:/)
      assert.match(token.content, /accDescr:/)
      assert.doesNotMatch(token.content, /%%\{|classDef|<br|^\s*click\s/m)
      const parsed = await mermaid.parse(token.content)
      report.diagrams.push({article: name, type: parsed.diagramType, sha256: hash(token.content)})
    } else {
      await compileCode({value:token.content, lang, meta:meta.join(' ')})
      ordinaryBlocks++
    }
  }
  report.articles.push({id:data.id, sha256:hash(text), source})
}
for (const entry of snippets) {
  const name = entry.doc.endsWith('service-level-signals.md') ? articles[0][0] : articles[1][0]
  const text = readFileSync(join(packageRoot, 'articles', name), 'utf8')
  const marker = `<!-- snippet: ${entry.id} -->`
  assert.equal(text.split(marker).length, 2)
  const block = md.parse(text.slice(text.indexOf(marker)+marker.length), {})[0]
  assert.equal(block.type, 'fence')
  const {result} = await compileCode({value:block.content, lang:entry.language, meta:'steps'})
  const source = readFileSync(join(packageRoot, entry.source), 'utf8')
  assert.equal(hash(source), entry.sourceSha256)
  assert.equal(result.code.trimEnd(), source.trimEnd())
  assert.ok(result.annotations.filter(a=>a.name==='step').length >= 3)
  report.snippets.push({id:entry.id, sourceSha256:hash(source), cleanCodeSha256:hash(result.code),
    steps:result.annotations.filter(a=>a.name==='step').length})
}
const configPath = 'labs/cloud-reliability-lab/pod-spec-fragment.yaml'
const config = readFileSync(join(packageRoot, configPath), 'utf8')
const parsedConfig = yaml.load(config)
assert.equal(parsedConfig.terminationGracePeriodSeconds, 30)
assert.equal(parsedConfig.containers[0].readinessProbe.failureThreshold, 1)
const body = readFileSync(join(packageRoot, 'articles/readiness-draining.md'), 'utf8')
assert.equal(body.split('```yaml\n')[1].split('```')[0], config)
report.yaml = {source: configPath, sha256:hash(config), status:'syntax-and-exact-text-only'}
report.codeBlocksCompiled = ordinaryBlocks
dom.window.close()
writeFileSync(join(packageRoot, 'records/author-static.json'), JSON.stringify(report,null,2)+'\n')
console.log(JSON.stringify({status:report.status, articles:report.articles.length,
  diagrams:report.diagrams.length, codeBlocks:ordinaryBlocks, snippets:report.snippets.length,
  yaml:report.yaml.status}))
