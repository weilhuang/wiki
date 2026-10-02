import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join, resolve, relative } from 'node:path'
import { site } from '../site.config.mjs'
import { JSDOM } from 'jsdom'
import { syncNotFoundMetadata } from '../docs/.vitepress/theme/not-found-metadata.mjs'
import { readChapters, aliasEntries, chapterNavigation } from './curriculum.mjs'
const dist = resolve('docs/.vitepress/dist')
const walk = dir => readdirSync(dir).flatMap(name => { const path = join(dir, name); return statSync(path).isDirectory() ? walk(path) : [path] })
const files = walk(dist)
const pages = files.filter(file => file.endsWith('.html'))
const errors = []
for (const path of pages) {
  const text = readFileSync(path, 'utf8')
  const pageUrl = new URL(relative(dist, path), site.url)
  for (const match of text.matchAll(/(?:href|src)="([^"]+)"/g)) {
    const raw = match[1].replace(/&amp;/g, '&')
    if (!raw || /^(?:data:|mailto:|tel:)/.test(raw)) continue
    const url = new URL(raw, pageUrl)
    if (url.origin !== new URL(site.url).origin) continue
    if (!url.pathname.startsWith(site.base)) { errors.push(`${relative(dist, path)}: link escapes base: ${raw}`); continue }
    const urlPath = decodeURIComponent(url.pathname.slice(site.base.length))
    const target = resolve(dist, urlPath.endsWith('/') || !urlPath ? `${urlPath}index.html` : urlPath)
    if (!target.startsWith(`${dist}/`)) { errors.push(`Unsafe local path: ${raw}`); continue }
    if (!existsSync(target)) errors.push(`${relative(dist, path)}: missing ${raw}`)
    else if (url.hash && target.endsWith('.html')) {
      const targetHtml = readFileSync(target, 'utf8')
      const id = decodeURIComponent(url.hash.slice(1))
      // Tag filters intentionally use URL fragments as selected UI state.
      if (!target.endsWith('/tags.html') && !targetHtml.includes(`id="${id}"`)) errors.push(`${relative(dist, path)}: missing anchor ${raw}`)
    }
  }
  if (!text.includes('lang="zh-CN"')) errors.push(`${path}: missing document language`)
}
for (const file of ['feed.xml', 'sitemap.xml', '404.html', '.nojekyll']) if (!existsSync(join(dist, file))) errors.push(`Missing ${file}`)
const feed = readFileSync(join(dist, 'feed.xml'), 'utf8')
const map = readFileSync(join(dist, 'sitemap.xml'), 'utf8')
if (!feed.includes(site.url) || !map.includes(site.url)) errors.push('RSS or sitemap missing deployment base')
const notFoundDom = new JSDOM(readFileSync(join(dist, '404.html'), 'utf8'))
const notFoundDocument = notFoundDom.window.document
if (notFoundDocument.querySelector('meta[name=robots]')?.content !== 'noindex' || notFoundDocument.querySelector('link[rel=canonical]')) errors.push('Generated default 404 must be noindex without canonical')
syncNotFoundMetadata(notFoundDocument, true)
syncNotFoundMetadata(notFoundDocument, true)
if (notFoundDocument.querySelectorAll('meta[name=robots]').length !== 1) errors.push('404 robots metadata duplicated during client initialization')
syncNotFoundMetadata(notFoundDocument, false)
if (notFoundDocument.querySelector('meta[name=robots]')) errors.push('404 robots metadata survives navigation to a normal page')
notFoundDom.window.close()

const chapters = readChapters(process.cwd(), { strict:true })
const legacyAnchors = JSON.parse(readFileSync('tests/fixtures/legacy-anchors.json','utf8'))
for (const chapter of chapters) {
  const html = readFileSync(join(dist, chapter.url.slice(1)), 'utf8')
  const canonical = new URL(chapter.url.slice(1), site.url).href
  const dom = new JSDOM(html)
  if (dom.window.document.querySelector('link[rel=canonical]')?.getAttribute('href') !== canonical) errors.push(`${chapter.source}: incorrect canonical`)
  const navigation = chapterNavigation(chapter, chapters)
  for (const direction of ['prev','next']) {
    const href = dom.window.document.querySelector(`a.pager-link.${direction}`)?.getAttribute('href')
    const expected = navigation[direction] ? `${site.base}${navigation[direction].link.slice(1)}` : undefined
    if (href !== expected) errors.push(`${chapter.source}: incorrect ${direction} chapter link`)
  }
  dom.window.close()
}
for (const alias of aliasEntries()) {
  const file = join(dist, alias.from.endsWith('/') ? `${alias.from}index.html` : alias.from)
  const html = readFileSync(file, 'utf8')
  if (!html.includes('noindex,follow') || !html.includes('location.replace(') || !html.includes('+location.search+location.hash')) errors.push(`${alias.from}: incomplete compatibility redirect`)
  if (!html.includes(new URL(alias.to.slice(1),site.url).href)) errors.push(`${alias.from}: incorrect target canonical`)
  const target = readFileSync(join(dist, alias.to.endsWith('/') ? `${alias.to}index.html` : alias.to), 'utf8')
  for (const id of legacyAnchors[alias.from] || []) if (!target.includes(`id="${id}"`)) errors.push(`${alias.from}: legacy anchor lost: ${id}`)
  if (map.includes(new URL(alias.from.slice(1),site.url).href) || feed.includes(new URL(alias.from.slice(1),site.url).href)) errors.push(`${alias.from}: legacy URL leaked into sitemap/RSS`)
}
const feedLinks = [...feed.matchAll(/<item><title>.*?<\/title><link>(.*?)<\/link>/g)].map(match=>match[1])
if (feedLinks.length !== chapters.length || new Set(feedLinks).size !== chapters.length) errors.push('RSS must contain each canonical chapter exactly once')

if (errors.length) throw new Error(errors.join('\n'))
console.log(`Output: ${pages.length} HTML pages, internal links/assets, language, canonical curriculum, legacy anchors, feed, sitemap and 404 passed`)
