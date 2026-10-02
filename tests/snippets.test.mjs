import test from'node:test'
import assert from'node:assert/strict'
import{readFileSync,readdirSync}from'node:fs'
import{createHash}from'node:crypto'
import{compileCode}from'../scripts/render-codehike.mjs'
const dedent=text=>{const lines=text.replace(/\n$/,'').split('\n'),indent=Math.min(...lines.filter(l=>l.trim()).map(l=>l.match(/^ */)[0].length));return lines.map(l=>l.slice(Math.min(l.match(/^ */)[0].length,indent))).join('\n')+'\n'}
test('Declared Code Hike excerpts match the exact fixed source snapshot and selected lines',async()=>{
 for(const file of readdirSync('content/snippets').filter(f=>f.endsWith('.json')))for(const entry of JSON.parse(readFileSync('content/snippets/'+file,'utf8'))){
  const source=readFileSync(entry.source,'utf8');assert.equal(createHash('sha256').update(source).digest('hex'),entry.sourceSha256,entry.id+' source snapshot stale')
  const doc=readFileSync(entry.doc,'utf8'),marker=`<!-- snippet: ${entry.id} -->`;assert.equal(doc.split(marker).length,2,'one explicit snippet marker')
  const block=doc.slice(doc.indexOf(marker)+marker.length).match(/^\s*```java steps\n([\s\S]*?)\n```/);assert.ok(block,entry.id)
  const result=(await compileCode({value:block[1]+'\n',lang:entry.language,meta:'steps'})).result
  const selected=entry.lines?source.split('\n').slice(entry.lines[0]-1,entry.lines[1]).join('\n')+'\n':source
  assert.equal(dedent(result.code),dedent(selected),entry.id+' does not match declared source')
 }
})
