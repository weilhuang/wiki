import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { aliasEntries } from './knowledge.mjs'
import { site } from '../site.config.mjs'
const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
const scriptJson=value=>JSON.stringify(value).replaceAll('<','\\u003c')
export function legacyHtml(alias,anchors=[],config=site){
  const target=`${config.base}${alias.to.slice(1)}`,canonical=new URL(alias.to.slice(1),config.url).href
  const anchorMap=Object.fromEntries(Object.entries(alias.anchors||{}).map(([key,value])=>[key,config.base+value.slice(1)]))
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,follow"><link rel="canonical" href="${escape(canonical)}"><title>知识页面已归位 · ${escape(config.title)}</title></head><body><main><h1>知识页面已归位</h1><p>正文已进入领域目录，原有知识、反例与实验继续保留。</p><p><a href="${escape(target)}">继续阅读</a></p>${anchors.length?`<noscript><h2>原书签定位</h2><p>选择原小节，前往新的知识位置。</p><ul>${anchors.map(id=>`<li id="${escape(id)}"><a href="${escape(anchorMap[id]||target+'#'+encodeURIComponent(id))}">${escape(id)}</a></li>`).join('')}</ul></noscript>`:''}</main><script>const targets=${scriptJson(anchorMap)};let id='';try{id=decodeURIComponent(location.hash.slice(1))}catch{}const mapped=Object.hasOwn(targets,id)?targets[id]:null;if(mapped){const parts=mapped.split('#');location.replace(parts[0]+location.search+(parts[1]?'#'+parts[1]:''))}else{location.replace(${scriptJson(target)}+location.search+location.hash)}</script></body></html>\n`
}
export function writeLegacyPages(outDir){
  const anchors=JSON.parse(readFileSync(new URL('../tests/fixtures/knowledge-legacy-anchors.json',import.meta.url),'utf8'))
  for(const alias of aliasEntries()){const path=join(outDir,alias.from.endsWith('/')?`${alias.from}index.html`:alias.from);mkdirSync(dirname(path),{recursive:true});writeFileSync(path,legacyHtml(alias,anchors[alias.from]||[]))}
}
