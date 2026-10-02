import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import matter from 'gray-matter'

import { site } from '../site.config.mjs'
export { site }
export function readPosts(root = process.cwd()) {
  const dir = join(root, 'docs/blog')
  return readdirSync(dir).filter(file => file.endsWith('.md') && file !== 'index.md').map(file => {
    const { data, content } = matter(readFileSync(join(dir, file), 'utf8'))
    if (data.draft) throw new Error(`${file}: 未发布草稿请放到 docs 目录之外`)
    for (const key of ['title', 'description', 'date', 'category']) {
      if (!data[key] || typeof data[key] !== 'string') throw new Error(`${file}: ${key} 必须是非空字符串（日期请加引号）`)
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(data.date) || Number.isNaN(Date.parse(data.date))) throw new Error(`${file}: 日期格式无效`)
    if (!Array.isArray(data.tags) || !data.tags.length || data.tags.some(t => typeof t !== 'string' || !t.trim())) throw new Error(`${file}: tags 必须为非空字符串数组`)
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*\.md$/.test(file)) throw new Error(`${file}: slug 必须使用小写 kebab-case`)
    const headings = content.match(/^# /gm) || []
    if (headings.length !== 1) throw new Error(`${file}: 正文需要恰好一个一级标题`)
    const plain = content.replace(/```[\s\S]*?```/g, '').replace(/<[^>]*>/g, '')
    const chinese = (plain.match(/[\u3400-\u9fff]/g) || []).length
    const words = (plain.match(/[A-Za-z0-9_]+/g) || []).length
    return { title: data.title, description: data.description, date: data.date, category: data.category, tags: [...new Set(data.tags)], order: Number(data.order) || 100, minutes: Math.max(1, Math.ceil(chinese / 450 + words / 220)), url: `/blog/${file.replace(/\.md$/, '.html')}` }
  }).sort((a, b) => b.date.localeCompare(a.date) || a.order - b.order || a.title.localeCompare(b.title, 'zh-CN'))
}
export function escapeXml(value) {
  return String(value).replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[char]))
}
export function rss(posts) {
  const e = escapeXml
  return `<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>${e(site.title)}</title><link>${e(site.url)}</link><description>后端开发与系统设计的技术笔记</description><language>zh-CN</language><atom:link href="${site.url}feed.xml" rel="self" type="application/rss+xml"/>${posts.map(post => {
    const url = new URL(post.url.slice(1), site.url).href
    return `<item><title>${e(post.title)}</title><link>${e(url)}</link><guid isPermaLink="true">${e(url)}</guid><description>${e(post.description)}</description><pubDate>${new Date(`${post.date}T00:00:00Z`).toUTCString()}</pubDate>${post.tags.map(tag => `<category>${e(tag)}</category>`).join('')}</item>`
  }).join('')}</channel></rss>\n`
}
