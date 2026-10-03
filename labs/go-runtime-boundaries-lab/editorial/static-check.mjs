import {createRequire} from 'node:module';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,join,posix} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const root=resolve(process.argv[2]||'.');
const wiki=resolve(process.argv[3]);
const require=createRequire(join(wiki,'package.json'));
const matter=require('gray-matter');
const MarkdownIt=require('markdown-it');
const {JSDOM}=require('jsdom');
const {compileCode}=await import(pathToFileURL(join(wiki,'scripts/render-codehike.mjs')));
const {validateTopic,readTopics}=await import(pathToFileURL(join(wiki,'scripts/knowledge.mjs')));
const dom=new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window=dom.window;globalThis.document=dom.window.document;
const {default:mermaid}=await import(pathToFileURL(require.resolve('mermaid')));
mermaid.initialize({startOnLoad:false,securityLevel:'strict',htmlLabels:false});
const md=new MarkdownIt();
const mappings=[
 ['channel-memory-ownership.md','go.channel-memory-ownership','knowledge/go/concurrency/channel-memory-ownership.md','go-runtime.roundtrip','ownership.go','func RoundTrip()'],
 ['scheduler-netpoll-diagnosis.md','go.runtime-wait-diagnosis','knowledge/go/runtime/scheduler-netpoll-diagnosis.md','go-runtime.queued-work','cmd/diagnose/main.go','func queuedWork(']
];
const sha=x=>createHash('sha256').update(x).digest('hex');
const sources=JSON.parse(readFileSync(join(root,'sources.json'),'utf8'));
const topics=readTopics(wiki);
const ids=new Set([...topics.map(t=>t.id),...mappings.map(x=>x[1])]);
const canonical=new Set([...topics.map(t=>t.source),...mappings.map(x=>x[2])]);
const terms=JSON.parse(readFileSync(join(wiki,'content/terms.json'),'utf8'));
const result={status:'pass',articles:[],diagrams:0,codeHikeFences:0,steps:0,links:0};
const snippets=[];
for(const[file,id,source,snippetId,labfile,prefix]of mappings){
 const path=join(root,'articles',file),bytes=readFileSync(path,'utf8');
 const {data,content}=matter(bytes);
 assert.equal(data.id,id);assert.equal(data.status,'review');assert.equal(data.reviewedAt,undefined);
 validateTopic({...data,source},{terms});
 for(const relation of ['requires','recommendedBefore','related','contrastsWith'])for(const edge of data[relation]||[])assert(ids.has(edge.id),`missing relation ${edge.id}`);
 for(const id of data.sourceRefs)assert(sources.some(s=>s.id===id),`missing source ${id}`);
 const tokens=md.parse(content,{});
 assert.equal(tokens.filter(t=>t.type==='heading_open'&&t.tag==='h1').length,1);
 const fences=tokens.filter(t=>t.type==='fence');
 for(const fence of fences){
  if(fence.info==='mermaid'){
   assert.match(fence.content,/accTitle:/);assert.match(fence.content,/accDescr:/);
   assert.doesNotMatch(fence.content,/%%\{|<[^>]+>|\bclick\s|classDef\s/);
   assert.ok(await mermaid.parse(fence.content));result.diagrams++;continue;
  }
  const [lang,...meta]=fence.info.split(/\s+/);
  const compiled=await compileCode({value:fence.content,lang,meta:meta.join(' ')});
  assert.match(compiled.html,/data-codehike-version="1.1.0"/);result.codeHikeFences++;
  if(meta.includes('steps')){
   const step=compiled.result.annotations.filter(a=>a.name==='step');assert.ok(step.length);result.steps+=step.length;
   const raw=readFileSync(join(root,'labs/go-runtime-boundaries-lab',labfile),'utf8');
   const lines=raw.split('\n');const start=lines.findIndex(l=>l.startsWith(prefix));assert.ok(start>=0);
   let end=start,depth=0;
   for(;end<lines.length;end++){depth+=(lines[end].match(/\{/g)||[]).length-(lines[end].match(/\}/g)||[]).length;if(depth===0)break;}
   const extracted=lines.slice(start,end+1).join('\n');
   assert.equal(compiled.result.code.trimEnd(),extracted);
   snippets.push({id:snippetId,article:'articles/'+file,file:labfile,lines:[start+1,end+1],transform:'none',sourceSha256:sha(raw),cleanCodeSha256:sha(compiled.result.code),source:'labs/go-runtime-boundaries-lab/'+labfile,doc:'docs/'+source,language:'go'});
  }
 }
 for(const token of tokens.filter(t=>t.type==='inline'))for(const child of token.children||[]){
  if(child.type!=='link_open')continue;const href=child.attrGet('href');if(!href||/^(https:|#)/.test(href))continue;
  if(href==='/examples/go-runtime-boundaries-lab.zip'){result.links++;continue;}
  let target=href.split('#')[0];if(target.startsWith('/'))target=target.slice(1);else target=posix.normalize(posix.join(posix.dirname(source),target));target=target.replace(/\.html$/,'.md');
  assert(canonical.has(target),`missing canonical ${href}`);result.links++;
 }
 result.articles.push({id,source:'docs/'+source,sha256:sha(bytes),h1:1});
}
assert.equal(result.diagrams,2);assert.equal(snippets.length,2);
writeFileSync(join(root,'snippets.json'),JSON.stringify(snippets,null,2)+'\n');
writeFileSync(join(root,'checks/static-result.json'),JSON.stringify(result,null,2)+'\n');
dom.window.close();console.log(JSON.stringify(result));
