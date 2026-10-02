import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { runInNewContext } from 'node:vm'
import { curriculum, validateStructure, sourceUrl, readChapters, chapterNavigation, validateReadiness } from '../scripts/curriculum.mjs'
import { legacyHtml } from '../scripts/legacy.mjs'
import { JSDOM } from 'jsdom'

test('Curriculum has three ordered closed paths and canonical routes', () => {
  assert.equal(validateStructure(),true)
  assert.equal(curriculum.chapters.length,15)
  assert.equal(sourceUrl('learn/go-service-lifecycle/index.md'),'/learn/go-service-lifecycle/')
  const chapters = curriculum.chapters.map(c=>({...c,title:c.id,url:sourceUrl(c.source)}))
  for(const path of curriculum.paths) {
    const own=chapters.filter(c=>c.pathId===path.id)
    assert.equal(chapterNavigation(own[0],chapters).prev,false)
    assert.equal(chapterNavigation(own.at(-1),chapters).next,false)
    for(let i=1;i<own.length;i++) assert.equal(chapterNavigation(own[i],chapters).prev.link,own[i-1].url)
  }
})
test('Curriculum rejects cycles, missing prerequisites, duplicate routes and stage drift', () => {
  let copy=structuredClone(curriculum);copy.chapters[0].prerequisites=[copy.chapters[1].id];assert.throws(()=>validateStructure(copy),/存在环/)
  copy=structuredClone(curriculum);copy.chapters[0].prerequisites=['missing'];assert.throws(()=>validateStructure(copy),/未知先修/)
  copy=structuredClone(curriculum);copy.chapters[1].source=copy.chapters[0].source;assert.throws(()=>validateStructure(copy),/重复章节 route/)
  copy=structuredClone(curriculum);copy.paths[0].stages[0].chapters.reverse();assert.throws(()=>validateStructure(copy),/阶段与章节/)
})
test('Missing chapters fail publication; preview never manufactures placeholder files', () => {
  const root=mkdtempSync(join(tmpdir(),'wiki-curriculum-'))
  try {
    mkdirSync(join(root,'docs/learn'),{recursive:true})
    assert.deepEqual(readChapters(root),[])
    assert.throws(()=>validateReadiness(root),/缺少 15 章/)
    writeFileSync(join(root,'docs/learn/unregistered.md'),'# Hidden draft\n')
    assert.throws(()=>readChapters(root),/未登记学习页面/)
  } finally { rmSync(root,{recursive:true,force:true}) }
})
test('Legacy compatibility has canonical/noindex, safe base and no-JS deep-link targets', () => {
  const config={title:'A < B',url:'https://example.com/notes/',base:'/notes/'}
  const html=legacyHtml({from:'/blog/old.html',to:'/learn/path/chapter.html'},['共享事务'],config)
  const dom=new JSDOM(html)
  assert.equal(dom.window.document.querySelector('link[rel=canonical]').href,'https://example.com/notes/learn/path/chapter.html')
  assert.equal(dom.window.document.querySelector('meta[name=robots]').content,'noindex,follow')
  assert.match(html,/location\.replace\("\/notes\/learn\/path\/chapter\.html"\+location\.search\+location\.hash\)/)
  assert.match(html,/id="共享事务"/)
  assert.match(html,/chapter\.html#%E5%85%B1/)
  assert.equal(dom.window.document.title,'章节已归入学习路径 · A < B')
  let replaced
  runInNewContext(dom.window.document.querySelector('script').textContent, {location:{search:'?from=bookmark&next=https%3A%2F%2Foutside.example',hash:'#共享事务',replace:value=>{replaced=value}}})
  assert.equal(replaced,'/notes/learn/path/chapter.html?from=bookmark&next=https%3A%2F%2Foutside.example#共享事务')
  dom.window.close()
})

test('Complete prose still cannot publish without verified source-bound experiment evidence', () => {
  const root=mkdtempSync(join(tmpdir(),'wiki-ready-'))
  const model=structuredClone(curriculum)
  try {
    for(const source of [...model.requiredPages,...model.paths.map(p=>p.introSource),...model.chapters.map(c=>c.source)]) {
      const path=join(root,'docs',source);mkdirSync(path.slice(0,path.lastIndexOf('/')),{recursive:true})
      writeFileSync(path,'---\ntitle: Fixture\ndescription: Synthetic test only\ndate: "2026-10-02"\ntags: [test]\nobjectives: [test]\nversions: [test]\n---\n# Fixture\n\n```sh\n# This shell comment is not a document title\necho test\n```\n')
    }
    for(const c of model.chapters)c.contentStatus='ready'
    assert.throws(()=>validateReadiness(root,model),/缺少执行证据/)
    mkdirSync(join(root,'evidence'),{recursive:true});mkdirSync(join(root,'docs/public/examples'),{recursive:true})
    const artifact=Buffer.from('Synthetic artifact hash fixture, not a real experiment archive')
    for(const reference of new Set(model.chapters.map(c=>c.evidence))) {
      const group=model.chapters.filter(c=>c.evidence===reference)
      const target=group[0].practice.slice(1);writeFileSync(join(root,'docs/public',target),artifact)
      const evidence={status:'partial',chapterIds:group.map(c=>c.id),versions:['fixture'],commands:[{command:'fixture',exitCode:0}],scope:['fixture'],notCovered:[],artifacts:[{path:target,sha256:createHash('sha256').update(artifact).digest('hex')}]}
      writeFileSync(join(root,reference),JSON.stringify(evidence))
    }
    assert.throws(()=>validateReadiness(root,model),/尚未 verified/)
    for(const reference of new Set(model.chapters.map(c=>c.evidence))) {
      const file=join(root,reference);const evidence=JSON.parse(readFileSync(file,'utf8'));evidence.status='verified';writeFileSync(file,JSON.stringify(evidence))
    }
    assert.equal(validateReadiness(root,model).length,15)
    writeFileSync(join(root,'docs/public',model.chapters[0].practice),'Modified artifact')
    assert.throws(()=>validateReadiness(root,model),/执行证据不一致/)
  } finally {rmSync(root,{recursive:true,force:true})}
})
