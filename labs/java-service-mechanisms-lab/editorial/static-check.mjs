import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const root = path.dirname(new URL(import.meta.url).pathname);
const wiki = process.argv[2];
if (!wiki) throw new Error('Usage: node static-check.mjs <existing-wiki-checkout>');
const require = createRequire(path.join(wiki,'package.json'));
const matter = require('gray-matter');
const MarkdownIt = require('markdown-it');
const {JSDOM} = require('jsdom');
const {compileCode} = await import(pathToFileURL(path.join(wiki,'scripts/render-codehike.mjs')));
const {validateTopic, readTopics, validateStructure} = await import(pathToFileURL(path.join(wiki,'scripts/knowledge.mjs')));
const terms = JSON.parse(fs.readFileSync(path.join(wiki,'content/terms.json')));
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window; globalThis.document = dom.window.document;
const {default:mermaid} = await import(pathToFileURL(require.resolve('mermaid')));
mermaid.initialize({startOnLoad:false,securityLevel:'strict',htmlLabels:false});
const md = new MarkdownIt();
const mappings = {'jmm-safe-publication.md':'knowledge/java/juc-foundations/jmm-safe-publication.md','executor-admission.md':'knowledge/java/juc-execution/executor-admission.md','thread-gc-diagnosis.md':'knowledge/java/jvm-diagnostics/thread-gc-diagnosis.md'};
const snippets = JSON.parse(fs.readFileSync(path.join(root,'snippets.json')));
const hash = x=>createHash('sha256').update(x).digest('hex');
const result = {status:'pass',scope:'Metadata, relations, direct links, pinned Mermaid parse and Code Hike compilation, exact source snippet identity; no site build or browser review',articles:[],diagrams:[],code:[]};
const topics = [];
const existing = readTopics(wiki);
const routes = new Set([...existing.map(x=>x.source),...Object.values(mappings)]);
for (const [filename,canonical] of Object.entries(mappings)) {
 const text=fs.readFileSync(path.join(root,'articles',filename),'utf8');
 const {data,content}=matter(text);
 const topic={...data,source:canonical}; validateTopic(topic,{terms});topics.push(topic);
 const tokens=md.parse(content,{});
 assert.equal(tokens.filter(t=>t.type==='heading_open'&&t.tag==='h1').length,1);
 for(const token of tokens.filter(t=>t.type==='fence')) {
  if(token.info==='mermaid') {
   assert.match(token.content,/accTitle:/);assert.match(token.content,/accDescr:/);assert.doesNotMatch(token.content,/%%\{init|classDef|click /);
   const parsed=await mermaid.parse(token.content);result.diagrams.push({article:filename,type:parsed.diagramType,sha256:hash(token.content)});
  } else {
   const [lang,meta='']=token.info.split(' ');
   const {result:r,html}=await compileCode({value:token.content,lang,meta});
   assert.ok(html.includes('data-codehike-version="1.1.0"'));
   result.code.push({article:filename,lang,steps:r.annotations.filter(a=>a.name==='step').map(a=>[a.fromLineNumber,a.toLineNumber]),cleanSha256:hash(r.code)});
  }
 }
 for(const t of tokens.filter(t=>t.type==='inline')) for(const link of (t.children||[]).filter(t=>t.type==='link_open')) {
  const href=link.attrGet('href');if(!href||href.startsWith('https:')||href.startsWith('#')||href.startsWith('/examples/'))continue;
  const resolved=path.posix.normalize(path.posix.join(path.posix.dirname(canonical),href.split('#')[0])).replace(/\.html$/,'.md');
  assert.ok(routes.has(resolved),'Missing link '+filename+': '+href+' -> '+resolved);
 }
 result.articles.push({file:'articles/'+filename,id:data.id,canonical,sha256:hash(text)});
}
validateStructure([...existing,...topics],{terms,routes:[]});
for(const entry of snippets) {
 const article=fs.readFileSync(path.join(root,entry.article),'utf8');
 const piece=article.split('<!-- snippet: '+entry.id+' -->')[1];assert.ok(piece,entry.id);
 const token=md.parse(piece,{}).find(t=>t.type==='fence');const {result:r}=await compileCode({value:token.content,lang:'java',meta:'steps'});
 const source=fs.readFileSync(path.join(root,'labs/java-service-mechanisms-lab',entry.file));assert.equal(hash(source),entry.sourceSha256);
 let code=source.toString().split('\n').slice(entry.lines[0]-1,entry.lines[1]).join('\n');
 if(entry.transform==='dedent') { const margin=Math.min(...code.split('\n').filter(x=>x.trim()).map(x=>x.match(/^ */)[0].length));code=code.split('\n').map(x=>x.slice(margin)).join('\n'); }
 assert.equal(r.code,code+'\n',entry.id+' differs from source');assert.equal(hash(r.code),entry.cleanCodeSha256);
}
dom.window.close();
fs.writeFileSync(path.join(root,'static-check.json'),JSON.stringify(result,null,2)+'\n');
console.log('PASS: all authored diagrams, Code Hike snippets, metadata, relations and links');
