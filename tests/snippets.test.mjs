import test from'node:test'
import assert from'node:assert/strict'
import{readFileSync,readdirSync}from'node:fs'
import{createHash}from'node:crypto'
import{compileCode}from'../scripts/render-codehike.mjs'
import MarkdownIt from'markdown-it'
const dedent=text=>{
 const lines=text.replace(/\n$/,'').split('\n'), nonblank=lines.filter(l=>l.trim())
 let prefix=nonblank[0]?.match(/^[ \t]*/)[0]||''
 for(const line of nonblank)while(!line.startsWith(prefix))prefix=prefix.slice(0,-1)
 return lines.map(l=>l.trim()?l.slice(prefix.length):'').join('\n')+'\n'
}
test('Source excerpt indentation removes a common tab or space prefix without changing relative indentation',()=>{
 assert.equal(dedent('\tmethod {\n\t\tcall();\n\t}\n'),'method {\n\tcall();\n}\n')
 assert.equal(dedent('  method {\n    call();\n  }\n'),'method {\n  call();\n}\n')
 assert.notEqual(dedent('\tmethod {\n\tcall();\n\t}\n'),dedent('method {\n\tcall();\n}\n'))
})

const markdown=new MarkdownIt()
test('Declared Code Hike excerpts match the exact fixed source snapshot and selected lines',async()=>{
 for(const file of readdirSync('content/snippets').filter(f=>f.endsWith('.json')))for(const entry of JSON.parse(readFileSync('content/snippets/'+file,'utf8'))){
  const source=readFileSync(entry.source,'utf8');assert.equal(createHash('sha256').update(source).digest('hex'),entry.sourceSha256,entry.id+' source snapshot stale')
  const doc=readFileSync(entry.doc,'utf8'),marker=`<!-- snippet: ${entry.id} -->`;assert.equal(doc.split(marker).length,2,'one explicit snippet marker')
  const block=markdown.parse(doc.slice(doc.indexOf(marker)+marker.length),{})[0];assert.equal(block?.type,'fence',entry.id+' marker must immediately precede a code fence')
  const [language,...attributes]=block.info.trim().split(/\s+/);assert.equal(language,entry.language,entry.id+' declared language differs');assert.ok(attributes.includes('steps'),entry.id+' requires a step walkthrough')
  const result=(await compileCode({value:block.content,lang:entry.language,meta:'steps'})).result
  if(entry.cleanCodeSha256)assert.equal(createHash('sha256').update(result.code).digest('hex'),entry.cleanCodeSha256,entry.id+' compiled clean source changed')
  const selected=entry.lines?source.split('\n').slice(entry.lines[0]-1,entry.lines[1]).join('\n')+'\n':source
  assert.equal(dedent(result.code),dedent(selected),entry.id+' does not match declared source')
 }
})
