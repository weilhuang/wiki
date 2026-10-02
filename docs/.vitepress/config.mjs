import { defineConfig } from 'vitepress'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { readPosts, rss, site } from '../../scripts/content.mjs'
import { existsSync } from 'node:fs'
import { curriculum, chapterNavigation, sourceUrl } from '../../scripts/curriculum.mjs'
import { writeLegacyPages } from '../../scripts/legacy.mjs'
import { createCodeCache } from '../../scripts/code-cache.mjs'
import { wikiMarkdown } from '../../scripts/markdown-extensions.mjs'
import { tokenizeChinese } from '../../scripts/search.mjs'

const codeCache = await createCodeCache()
const posts = readPosts()
const available = source => existsSync(join(process.cwd(), 'docs', source))
const pathLink = path => sourceUrl(path.introSource)
const guideLinks = [
  { text: '知识地图', link: '/guide/knowledge-map.html', source: 'guide/knowledge-map.md' },
  { text: '全部学习路径', link: '/learn/', source: 'learn/index.md' },
  { text: '实验与评审', link: '/guide/practice.html', source: 'guide/practice.md' },
  { text: '后续规划', link: '/guide/roadmap.html', source: 'guide/roadmap.md' }
].filter(item => available(item.source)).map(({source,...item}) => item)
const sidebar = Object.fromEntries(curriculum.paths.map(path => [pathLink(path), [
  ...(available(path.introSource) ? [{ text: '路径导读', items: [{ text:path.title, link:pathLink(path) }] }] : []),
  ...path.stages.map(stage=>({ text:stage.title, collapsed:false, items:stage.chapters.map(id=>posts.find(p=>p.id===id)).filter(Boolean).map(chapter=>({text:`${chapter.order}. ${chapter.title}`,link:chapter.url})) })).filter(group=>group.items.length),
  { text:'相关路径', items:curriculum.paths.filter(p=>p.id!==path.id && available(p.introSource)).map(p=>({text:p.title,link:pathLink(p)})) }
].filter(group=>group.items.length)]))
sidebar['/'] = [{text:'阅读入口',items:guideLinks}, {text:'学习路径',items:curriculum.paths.filter(p=>available(p.introSource)).map(p=>({text:p.title,link:pathLink(p)}))}].filter(group=>group.items.length)
export default defineConfig({
  lang: 'zh-CN', title: site.title,
  description: '按先修、机制、实验与综合评审组织的后端工程知识站。',
  base: site.base, cleanUrls: false, lastUpdated: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${site.base}favicon.svg` }],
    ['link', { rel: 'alternate', type: 'application/rss+xml', title: `${site.title} RSS`, href: `${site.base}feed.xml` }],
    ['meta', { name: 'theme-color', content: '#3451b2' }],
    ['meta', { name: 'referrer', content: 'strict-origin-when-cross-origin' }]
  ],
  sitemap: { hostname: site.url, transformItems: items => items.filter(item => item.url !== '404.html' && !item.url.startsWith('blog/')) },
  transformPageData(pageData) {
    const chapter = posts.find(p=>p.source===pageData.relativePath)
    if (chapter) pageData.frontmatter = { ...pageData.frontmatter, ...chapterNavigation(chapter, posts) }
  },
  transformHead({ pageData }) {
    const path = pageData.relativePath.replace(/index\.md$/, '').replace(/\.md$/, '.html')
    if (path === '404.html') return [['meta', { name: 'robots', content: 'noindex' }]]
    return [['link', { rel: 'canonical', href: pageData.frontmatter.canonical ? new URL(pageData.frontmatter.canonical.replace(/^\//, ''), site.url).href : new URL(path, site.url).href }]]
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
      { text: '知识地图', link: '/guide/knowledge-map' },
      { text: '学习路径', activeMatch: '/learn/', items: [...curriculum.paths.filter(path=>available(path.introSource)).map(path=>({text:path.title,link:pathLink(path)})), ...(available('learn/index.md')?[{text:'全部学习路径',link:'/learn/'}]:[])] },
      ...(available('guide/practice.md') ? [{ text: '实验与评审', link: '/guide/practice' }] : []),
      { text: '标签', link: '/tags' },
      { text: '关于', link: '/about' }
    ],
    sidebar,
    socialLinks: [{ icon: 'github', link: site.repoUrl, ariaLabel: '查看 GitHub 源码' }],
    outline: { level: [2, 3], label: '本文目录' },
    docFooter: { prev: '上一章', next: '下一章' },
    lastUpdated: { text: '更新于', formatOptions: { dateStyle: 'medium' } },
    darkModeSwitchLabel: '主题', lightModeSwitchTitle: '切换到浅色模式', darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '章节目录', returnToTopLabel: '回到顶部', skipToContentLabel: '跳转到正文',
    notFound: { code: '404', title: '这页暂时找不到', quote: '链接可能已经移动。可以回到首页，或用搜索找找关键词。', linkLabel: '回到首页', linkText: '回到首页' },
    footer: { message: '基于 VitePress 构建', copyright: site.title },
    search: {
      provider: 'local',
      options: {
        detailedView: true,
        miniSearch: { options: { tokenize: tokenizeChinese }, searchOptions: { prefix: true, fuzzy: false, combineWith: 'AND' } },
        translations: {
          button: { buttonText: '搜索知识库', buttonAriaLabel: '搜索知识库' },
          modal: {
            displayDetails: '显示详细结果', resetButtonTitle: '清空搜索', backButtonTitle: '关闭搜索', noResultsText: '没有找到相关章节',
            footer: { selectText: '选择', selectKeyAriaLabel: '回车', navigateText: '切换', navigateUpKeyAriaLabel: '向上', navigateDownKeyAriaLabel: '向下', closeText: '关闭', closeKeyAriaLabel: 'Esc' }
          }
        }
      }
    }
  },
  buildEnd(config) {
    writeLegacyPages(config.outDir)
    writeFileSync(join(config.outDir, 'feed.xml'), rss(readPosts()))
    writeFileSync(join(config.outDir, 'robots.txt'), `User-agent: *\nAllow: ${site.base}\nSitemap: ${site.url}sitemap.xml\n`)
  }
})
