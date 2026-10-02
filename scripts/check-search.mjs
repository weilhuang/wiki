import{readFileSync,readdirSync}from'node:fs'
import{pathToFileURL}from'node:url'
import{resolve}from'node:path'
import MiniSearch from'minisearch'
import{tokenizeChinese}from'./search.mjs'
import{readTopics}from'./knowledge.mjs'
import{site}from'../site.config.mjs'
const dir='docs/.vitepress/dist/assets/chunks',file=readdirSync(dir).find(x=>x.startsWith('@localSearchIndexroot.')&&x.endsWith('.js'))
if(!file)throw Error('Missing actual generated MiniSearch index')
const json=(await import(pathToFileURL(resolve(dir,file)))).default,data=JSON.parse(json),topics=readTopics(),ids=Object.values(data.documentIds),canonical=new Set(topics.map(t=>site.base+t.url.slice(1)))
if(new Set(ids).size!==ids.length)throw Error('Duplicate search section IDs')
for(const id of ids)if(!canonical.has(id.split('#')[0]))throw Error('Noncanonical or auxiliary page in search: '+id)
for(const topic of topics)if(!ids.some(id=>id.split('#')[0]===site.base+topic.url.slice(1)))throw Error('Published topic absent from search: '+topic.id)
const index=MiniSearch.loadJSON(json,{fields:['title','titles','text'],storeFields:['title','titles'],tokenize:tokenizeChinese}),results=[]
for(const q of JSON.parse(readFileSync('content/search-intents.json','utf8'))){const topic=topics.find(t=>t.id===q.topic);if(!topic)throw Error('Unknown search contract topic '+q.topic);const expected=site.base+topic.url.slice(1)+'#'+q.anchor,hits=index.search(q.query,{prefix:true,fuzzy:false,combineWith:'AND'}).slice(0,3);if(!hits.some(hit=>hit.id===expected))throw Error(`Search missed intended section: ${q.query}`);results.push({query:q.query,expected,top:hits.map(h=>h.id)})}
if(index.search('没有此项内容xyz987654',{prefix:true,fuzzy:false,combineWith:'AND'}).length)throw Error('Nonsense query returned content')
console.log(`Search: ${ids.length} canonical sections, ${topics.length} topics, ${results.length} question/symbol targets in top 3, empty result passed`)
