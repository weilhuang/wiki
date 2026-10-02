import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,rmSync,readFileSync} from 'node:fs'
import {tmpdir}from'node:os'
import {join}from'node:path'
import {createHash}from'node:crypto'
import {runInNewContext}from'node:vm'
import {JSDOM}from'jsdom'
import {readTopics,validateTopic,validateStructure,validateEvidence,validateAliases,registries,paths}from'../scripts/knowledge.mjs'
import {legacyHtml}from'../scripts/legacy.mjs'
const fixture=(id,extra={})=>({id,source:`knowledge/java/collections/${id}.md`,kind:'concept',status:'published',title:id,description:'A synthetic fixture for model contracts',domain:'java',category:'collections',date:'2026-10-02',scope:'synthetic only',tags:{technology:['java'],task:['understand']},requires:[],sourceRefs:[],verificationRefs:[],...extra})
test('Knowledge has no fixed route count, chapter count, or unique route ownership',()=>{
 const topics=[fixture('one'),fixture('two'),fixture('three')]
 const route={id:'test',source:'paths/test.md',status:'published',entry:['basic'],goal:'goal',stages:[{title:'stage',task:'task',readings:[{topic:'one',role:'required',purpose:'purpose'}]}]}
 assert.equal(validateStructure(topics,{routes:[]}),true)
 assert.equal(validateStructure(topics,{routes:[route,{...route,id:'another',source:'paths/another.md'}]}),true)
 assert.equal(readTopics().some(t=>Object.hasOwn(t,'pathId')),false)
 assert.ok(paths.every(p=>p.stages.every(s=>s.task&&s.readings.every(r=>r.purpose))))
})
test('Strong prerequisites reject cycles and missing nodes, related links may form cycles',()=>{
 let topics=[fixture('one',{requires:[{id:'two',reason:'needs state'}]}),fixture('two',{requires:[{id:'one',reason:'needs input'}]})]
 assert.throws(()=>validateStructure(topics,{routes:[]}),/存在环/)
 topics=[fixture('one',{related:[{id:'two',reason:'comparison'}]}),fixture('two',{related:[{id:'one',reason:'comparison'}]})]
 assert.equal(validateStructure(topics,{routes:[]}),true)
 topics[0].requires=[{id:'missing',reason:'missing'}];assert.throws(()=>validateStructure(topics,{routes:[]}),/未知关系/)
 topics[0].requires=[{id:'two',reason:''}];assert.throws(()=>validateStructure(topics,{routes:[]}),/原因/)
})
test('Unknown taxonomy, status and duplicate routes fail; headings are not curriculum metadata',()=>{
 assert.throws(()=>validateTopic(fixture('one',{category:'nonexistent'})),/未知分类/)
 assert.throws(()=>validateTopic(fixture('one',{status:'verified'})),/编辑状态/)
 assert.throws(()=>validateTopic(fixture('one',{pathId:'course'})),/唯一路线/)
 assert.throws(()=>validateStructure([fixture('one'),fixture('two',{source:'knowledge/java/collections/one.md'})],{routes:[]}),/重复 canonical/)
})
test('A published concept needs no fake executable ZIP; executed claims bind exact source bytes',()=>{
 const root=mkdtempSync(join(tmpdir(),'wiki-evidence-'))
 try{
   const topic=fixture('one'),registry={sources:[],verification:[]};assert.equal(validateEvidence(root,[topic],registry),true)
   topic.kind='lab';assert.throws(()=>validateEvidence(root,[topic],registry),/实验教程/)
   topic.verificationRefs=['test.run'];registry.verification=[{id:'test.run',kind:'executed',status:'not-run',scope:['synthetic'],limitations:['not run']}]
   assert.equal(validateEvidence(root,[topic],registry),true)
   registry.verification[0].status='pass';assert.throws(()=>validateEvidence(root,[topic],registry),/源码与成功命令/)
   mkdirSync(join(root,'labs'));writeFileSync(join(root,'labs/sample.txt'),'fixed source')
   Object.assign(registry.verification[0],{sourceFiles:[{path:'labs/sample.txt',sha256:createHash('sha256').update('fixed source').digest('hex')}],commands:[{command:'synthetic assertion',exitCode:0}]})
   assert.equal(validateEvidence(root,[topic],registry),true)
   writeFileSync(join(root,'labs/sample.txt'),'changed source');assert.throws(()=>validateEvidence(root,[topic],registry),/stale/)
 }finally{rmSync(root,{recursive:true,force:true})}
})
test('All old experiment packages retain their source-bound evidence',()=>assert.equal(validateEvidence(process.cwd(),readTopics(),registries()),true))
test('Compatibility goes directly to canonical pages and preserves query/hash without open redirects',()=>{
 const config={title:'A < B',url:'https://example.com/notes/',base:'/notes/'}
 const alias={from:'/blog/old.html',to:'/knowledge/java/collections/one.html',anchors:{split:'/knowledge/java/collections/two.html#new-section'}}
 const html=legacyHtml(alias,['old','split'],config),dom=new JSDOM(html)
 assert.equal(dom.window.document.querySelector('link[rel=canonical]').href,'https://example.com/notes/knowledge/java/collections/one.html')
 assert.equal(dom.window.document.querySelector('meta[name=robots]').content,'noindex,follow')
 const script=dom.window.document.querySelector('script').textContent
 for(const [hash,expected]of [['#old','/notes/knowledge/java/collections/one.html?next=https%3A%2F%2Fevil.example#old'],['#split','/notes/knowledge/java/collections/two.html?next=https%3A%2F%2Fevil.example#new-section'],['#%broken','/notes/knowledge/java/collections/one.html?next=https%3A%2F%2Fevil.example#%broken']]){let actual;runInNewContext(script,{location:{hash,search:'?next=https%3A%2F%2Fevil.example',replace:x=>actual=x}});assert.equal(actual,expected)}
 assert.match(html,/two\.html#new-section/);assert.equal(dom.window.document.title,'知识页面已归位 · A < B');dom.window.close()
 const topics=[fixture('one')];assert.throws(()=>validateAliases([{from:'/old/',to:'/other/'}],topics),/未直达 canonical/)
})

test('Route and generated-view collisions fail before they can overwrite a topic',async()=>{
 const {validateOutputRoutes}=await import('../scripts/knowledge.mjs')
 const topics=[fixture('one')],route={id:'test',source:'paths/test.md',status:'published',entry:['basic'],goal:'goal',stages:[{title:'stage',task:'task',readings:[{topic:'one',role:'required',purpose:'purpose'}]}]}
 assert.throws(()=>validateStructure(topics,{routes:[route,{...route,id:'second'}]}),/重复路线 source/)
 assert.throws(()=>validateStructure(topics,{routes:[{...route,source:topics[0].source}]}),/覆盖知识正文/)
 assert.throws(()=>validateOutputRoutes(topics,{routes:[{...route,source:'knowledge/index.md'}],aliases:[]}),/生成页面路由冲突/)
 assert.throws(()=>validateOutputRoutes([fixture('one',{source:'knowledge/java/collections/index.md'})],{routes:[],aliases:[]}),/生成页面路由冲突/)
 assert.equal(validateOutputRoutes(topics,{routes:[route],aliases:[]}),true)
})
