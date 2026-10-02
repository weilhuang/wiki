import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { aliasEntries } from './curriculum.mjs'
import { site } from '../site.config.mjs'
const escape = value => String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
export function legacyHtml(alias, anchors = [], config = site) {
  const target = `${config.base}${alias.to.slice(1)}`
  const canonical = new URL(alias.to.slice(1), config.url).href
  // Both routes come from the validated manifest, never from a query parameter.
  const jsonTarget = JSON.stringify(target).replaceAll('<','\\u003c')
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,follow"><link rel="canonical" href="${escape(canonical)}"><title>章节已归入学习路径 · ${escape(config.title)}</title></head><body><main><h1>章节已归入学习路径</h1><p>内容现按学习路径组织，原有章节与实验继续保留。</p><p><a href="${escape(target)}">继续阅读</a></p>${anchors.length ? `<noscript><h2>原书签定位</h2><p>选择书签对应的小节，继续原来的阅读位置。</p><ul>${anchors.map(id=>`<li id="${escape(id)}"><a href="${escape(target)}#${encodeURIComponent(id)}">${escape(id)}</a></li>`).join('')}</ul></noscript>` : ''}</main><script>location.replace(${jsonTarget}+location.search+location.hash)</script></body></html>\n`
}
export function writeLegacyPages(outDir) {
  const anchors=JSON.parse(readFileSync(new URL('../tests/fixtures/legacy-anchors.json',import.meta.url),'utf8'))
  for(const alias of aliasEntries()) {
    const path=join(outDir,alias.from.endsWith('/')?`${alias.from}index.html`:alias.from)
    mkdirSync(dirname(path),{recursive:true});writeFileSync(path,legacyHtml(alias,anchors[alias.from]||[]))
  }
}
