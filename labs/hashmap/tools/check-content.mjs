import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const root=path.resolve(process.argv[2]||path.join(import.meta.dirname,'..'));
const wiki=path.resolve(process.argv[3] || process.env.WIKI_REPO || (()=>{throw new Error('Set WIKI_REPO to an existing wiki checkout with installed Code Hike/Mermaid dependencies; this editorial check is not required to run the Java lab')})());
const require=createRequire(path.join(wiki,'package.json'));
const MarkdownIt=require('markdown-it');
const matter=require('gray-matter');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window=dom.window; globalThis.document=dom.window.document;
const {default: mermaid}=await import(pathToFileURL(path.join(wiki,'node_modules/mermaid/dist/mermaid.esm.mjs')));
mermaid.initialize({startOnLoad:false,securityLevel:'strict'});
const {compileCode}=await import(pathToFileURL(path.join(wiki,'scripts/render-codehike.mjs')));
const parser=new MarkdownIt();
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const dedent=x=>{
  const lines=x.replace(/\n$/,'').split('\n');
  const indent=Math.min(...lines.filter(l=>l.trim()).map(l=>l.match(/^ */)[0].length));
  return lines.map(l=>l.slice(Math.min(l.match(/^ */)[0].length,indent))).join('\n')+'\n';
};
const snippets=JSON.parse(fs.readFileSync(path.join(root,'snippets.json'),'utf8'));
const checks=[];
for(const name of ['hashmap.md','hashmap-source.md']) {
  const file=path.join(root,'docs',name); const body=fs.readFileSync(file,'utf8');
  const {data,content}=matter(body);
  assert.equal(data.status,'review');
  assert.equal((content.match(/^# /gm)||[]).length,1,'exactly one h1');
  let mermaidCount=0,stepsCount=0;
  for(const token of parser.parse(content,{})) {
    if(token.type!=='fence')continue;
    const [lang,...meta]=token.info.trim().split(/\s+/);
    if(lang==='mermaid'){
      assert.match(token.content,/accTitle:/);assert.match(token.content,/accDescr:/);
      await mermaid.parse(token.content);mermaidCount++;continue;
    }
    const {result,html}=await compileCode({value:token.content,lang,meta:meta.join(' ')});
    assert(html.includes('data-codehike-version="1.1.0"'));
    if(meta.includes('steps')){
      assert(result.annotations.some(a=>a.name==='step'));
      assert(!result.code.includes('!step')); stepsCount++;
    }
  }
  checks.push({file:'docs/'+name,sha256:hash(body),mermaidParsed:mermaidCount,codeHikeSteps:stepsCount});
}
for(const entry of snippets){
  const doc=fs.readFileSync(path.join(root,entry.doc),'utf8');
  const marker=`<!-- snippet: ${entry.id} -->`;
  assert(doc.includes(marker));
  const block=doc.slice(doc.indexOf(marker)+marker.length).match(/```java steps\n([\s\S]*?)\n```/);
  assert(block);
  const {result}=await compileCode({value:block[1]+'\n',lang:'java',meta:'steps'});
  let original=fs.readFileSync(path.join(root,entry.source),'utf8');
  if(entry.lines)original=original.split('\n').slice(entry.lines[0]-1,entry.lines[1]).join('\n')+'\n';
  assert.equal(dedent(result.code),dedent(original),'clean source mismatch '+entry.id);
  checks.push({snippet:entry.id,cleanSourceSHA256:hash(dedent(result.code)),source:entry.source,lines:entry.lines||null,steps:result.annotations.length});
}
const ga=fs.readFileSync(path.join(root,'sources/HashMap-jdk-21+35.java'));
const runtime=fs.readFileSync(path.join(root,'sources/HashMap-runtime-21.0.12.1.java'));
assert(ga.equals(runtime),'runtime-associated source differs from explained GA source');
checks.push({sourceBytesEqual:true,sha256:hash(ga)});
console.log(JSON.stringify({status:'pass',checks,limitations:['Mermaid parse only; page rendering and accessibility need site integration QA','Code Hike compiled with actual 1.1.0 dependency; no standalone browser interaction tested']},null,2));
