import { defineConfig } from 'vitepress'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { readPosts, rss, site } from '../../scripts/content.mjs'
import { createCodeCache } from '../../scripts/code-cache.mjs'
import { wikiMarkdown } from '../../scripts/markdown-extensions.mjs'
import { tokenizeChinese } from '../../scripts/search.mjs'

const codeCache = await createCodeCache()
const posts = readPosts()
const categories = [...new Set(posts.map(p => p.category))]
export default defineConfig({
  lang: 'zh-CN', title: site.title,
  description: '把后端开发中的机制、边界和取舍，整理成能反复查阅的技术笔记。',
  base: site.base, cleanUrls: false, lastUpdated: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${site.base}favicon.svg` }],
    ['link', { rel: 'alternate', type: 'application/rss+xml', title: `${site.title} RSS`, href: `${site.base}feed.xml` }],
    ['meta', { name: 'theme-color', content: '#3451b2' }],
    ['meta', { name: 'referrer', content: 'strict-origin-when-cross-origin' }]
  ],
  sitemap: { hostname: site.url },
  transformHead({ pageData }) {
    const path = pageData.relativePath.replace(/index\.md$/, '').replace(/\.md$/, '.html')
    if (path === '404.html') return [['meta', { name: 'robots', content: 'noindex' }]]
    return [['link', { rel: 'canonical', href: new URL(path, site.url).href }]]
  },
  vite: { plugins: [{ name: 'wiki-codehike-watch', enforce: 'pre', generateBundle(_options, bundle) { for (const file of Object.values(bundle)) { if (file.type === 'chunk' && Object.keys(file.modules).some(id => /node_modules\/(react|react-dom|codehike|@code-hike)\//.test(id))) throw new Error('Build-only Code Hike/React leaked into a runtime bundle') } }, async handleHotUpdate(ctx) { if (ctx.file.endsWith('.md')) await codeCache.refresh() } }] },
  markdown: {
    highlight: (code, lang) => codeCache.get(code, lang).html,
    config: md => wikiMarkdown(md, codeCache),
    codeCopyButtonTitle: '复制代码',
    lineNumbers: true,
    theme: { light: 'github-light', dark: 'github-dark' },
    container: { tipLabel: '提示', warningLabel: '注意', dangerLabel: '风险', infoLabel: '说明', detailsLabel: '展开细节' }
  },
  themeConfig: {
    logo: '/favicon.svg', siteTitle: site.title,
    nav: [
      { text: '知识地图', link: '/guide/knowledge-map', activeMatch: '/guide/' },
      { text: '文章', link: '/blog/', activeMatch: '/blog/' },
      { text: '标签', link: '/tags' },
      { text: '关于', link: '/about' }
    ],
    sidebar: [
      { text: '从这里开始', items: [{ text: '知识地图', link: '/guide/knowledge-map' }, { text: '全部文章', link: '/blog/' }] },
      ...categories.map(category => ({ text: category, collapsed: false, items: posts.filter(p => p.category === category).map(p => ({ text: p.title, link: p.url })) }))
    ],
    socialLinks: [{ icon: 'github', link: site.repoUrl, ariaLabel: '查看 GitHub 源码' }],
    outline: { level: [2, 3], label: '本文目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    lastUpdated: { text: '更新于', formatOptions: { dateStyle: 'medium' } },
    darkModeSwitchLabel: '主题', lightModeSwitchTitle: '切换到浅色模式', darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '文章目录', returnToTopLabel: '回到顶部', skipToContentLabel: '跳转到正文',
    notFound: { code: '404', title: '这页暂时找不到', quote: '链接可能已经移动。可以回到首页，或用搜索找找关键词。', linkLabel: '回到首页', linkText: '回到首页' },
    footer: { message: '基于 VitePress 构建', copyright: `${site.title} · <a href="${site.base}feed.xml">RSS</a>` },
    search: {
      provider: 'local',
      options: {
        detailedView: true,
        miniSearch: { options: { tokenize: tokenizeChinese }, searchOptions: { prefix: true, fuzzy: false, combineWith: 'AND' } },
        translations: {
          button: { buttonText: '搜索笔记', buttonAriaLabel: '搜索笔记' },
          modal: {
            displayDetails: '显示详细结果', resetButtonTitle: '清空搜索', backButtonTitle: '关闭搜索', noResultsText: '没有找到相关笔记',
            footer: { selectText: '选择', selectKeyAriaLabel: '回车', navigateText: '切换', navigateUpKeyAriaLabel: '向上', navigateDownKeyAriaLabel: '向下', closeText: '关闭', closeKeyAriaLabel: 'Esc' }
          }
        }
      }
    }
  },
  buildEnd(config) {
    writeFileSync(join(config.outDir, 'feed.xml'), rss(readPosts()))
    writeFileSync(join(config.outDir, 'robots.txt'), `User-agent: *\nAllow: ${site.base}\nSitemap: ${site.url}sitemap.xml\n`)
  }
})
