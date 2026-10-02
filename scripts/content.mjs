import { readChapters } from './curriculum.mjs'
import { site } from '../site.config.mjs'
export { site }
// Kept as a compatibility name for tags and RSS; returns canonical chapters in curriculum order.
export function readPosts(root = process.cwd()) { return readChapters(root) }
export function escapeXml(value) {
  return String(value).replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[char]))
}
export function rss(posts) {
  const e = escapeXml
  return `<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>${e(site.title)}</title><link>${e(site.url)}</link><description>后端工程学习路径与实验章节</description><language>zh-CN</language><atom:link href="${site.url}feed.xml" rel="self" type="application/rss+xml"/>${[...posts].sort((a,b)=>b.date.localeCompare(a.date)||a.url.localeCompare(b.url)).map(post => {
    const url = new URL(post.url.slice(1), site.url).href
    return `<item><title>${e(post.title)}</title><link>${e(url)}</link><guid isPermaLink="true">${e(url)}</guid><description>${e(post.description)}</description><pubDate>${new Date(`${post.date}T00:00:00Z`).toUTCString()}</pubDate>${post.tags.map(tag => `<category>${e(tag)}</category>`).join('')}</item>`
  }).join('')}</channel></rss>\n`
}
