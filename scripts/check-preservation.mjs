import {readFileSync}from'node:fs'
import {createHash}from'node:crypto'
import {execFileSync}from'node:child_process'
import MarkdownIt from'markdown-it'
import matter from'gray-matter'
import{migrations}from'../content/migrations.mjs'
const baseline=JSON.parse(readFileSync('content/preserved-assets.json','utf8'))
for(const f of baseline.files){if(createHash('sha256').update(readFileSync(f.path)).digest('hex')!==f.sha256)throw Error(`Historical asset changed: ${f.path}`)}
const md=new MarkdownIt(),fences=text=>md.parse(matter(text).content,{}).filter(t=>t.type==='fence').map(t=>JSON.stringify({info:t.info,content:t.content})).sort()
for(const m of migrations){const before=execFileSync('git',['show',baseline.base+':docs/'+m.oldSource]).toString(),after=readFileSync('docs/'+m.source,'utf8');if(JSON.stringify(fences(before))!==JSON.stringify(fences(after)))throw Error(`Migrated code/diagram changed: ${m.id}`)}
const published=JSON.parse(readFileSync('content/preserved-topic-fences.json','utf8'))
for(const topic of published.topics){const current=fences(readFileSync('docs/'+topic.source,'utf8'));if(current.length!==topic.fenceCount||createHash('sha256').update(JSON.stringify(current)).digest('hex')!==topic.fencesSha256)throw Error(`Published code/diagram changed: ${topic.id}`)}
console.log(`Preserved: ${baseline.files.length} historical assets, ${migrations.length} migrated topics and all technical fences in ${published.topics.length} published baseline topics`)
