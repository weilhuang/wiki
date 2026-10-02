import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join, resolve, relative } from 'node:path'
import { site } from '../site.config.mjs'
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
if (errors.length) throw new Error(errors.join('\n'))
console.log(`Output: ${pages.length} HTML pages, internal links/assets, language, feed, sitemap and 404 passed`)
