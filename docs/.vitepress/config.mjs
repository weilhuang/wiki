import { defineConfig } from 'vitepress'
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { readPosts, rss, site } from '../../scripts/content.mjs'
import { existsSync } from 'node:fs'
import { taxonomy, paths, topicNavigation, sourceUrl } from '../../scripts/knowledge.mjs'
import { generateViews } from '../../scripts/generate-views.mjs'
import { addTopicContext } from '../../scripts/topic-context.mjs'
import { renderSearch } from '../../scripts/search.mjs'
import { writeLegacyPages } from '../../scripts/legacy.mjs'
import { managedPageHead } from '../../scripts/page-metadata.mjs'
import { notFoundRobots } from './theme/not-found-metadata.mjs'
import { createCodeCache } from '../../scripts/code-cache.mjs'
import { wikiMarkdown } from '../../scripts/markdown-extensions.mjs'
import { tokenizeChinese } from '../../scripts/search.mjs'

const posts = generateViews()
const codeCache = await createCodeCache()
const rootLinks=[{text:'知识目录',link:'/knowledge/'},{text:'学习路线',link:'/paths/'},{text:'场景与排障',link:'/cases/'},{text:'源码阅读',link:'/resources/source-reading.html'},{text:'实验与验证',link:'/resources/experiments.html'},{text:'复习与推理',link:'/resources/review.html'}]
const sidebar = Object.fromEntries(taxonomy.map(domain=>[`/knowledge/${domain.id}/`,[
  {text:domain.title,items:[{text:'领域导读',link:`/knowledge/${domain.id}/`}]},
  ...domain.categories.map(category=>({text:category.title,collapsed:false,items:[{text:'分类导读',link:`/knowledge/${domain.id}/${category.id}/`},...posts.filter(t=>t.domain===domain.id&&t.category===category.id).map(t=>({text:t.title,link:t.url}))]})).filter(group=>group.items.length>1),
  {text:'其他阅读入口',items:rootLinks}
]]))
sidebar['/']=[{text:'阅读入口',items:rootLinks},{text:'知识领域',collapsed:false,items:taxonomy.map(d=>({text:d.title,link:`/knowledge/${d.id}/`}))}]
sidebar['/paths/']=[{text:'目标路线',items:paths.map(p=>({text:p.title,link:sourceUrl(p.source)}))},{text:'其他入口',items:rootLinks}]
sidebar['/cases/']=[{text:'场景方案',items:posts.filter(t=>t.kind==='scenario').map(t=>({text:t.title,link:t.url}))},{text:'其他入口',items:rootLinks}]
export default defineConfig({
  lang: 'zh-CN', title: site.title,
  description: '按领域查找机制，沿学习路线建立联系，用源码和实验检验工程判断。',
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
    if (chapter) pageData.frontmatter = { ...pageData.frontmatter, ...topicNavigation(chapter, posts) }
    pageData.frontmatter.head = managedPageHead(pageData.relativePath, pageData.frontmatter, site.url)
  },
  transformHead({ pageData }) { return pageData.isNotFound ? [notFoundRobots] : [] },
  vite: { plugins: [{ name: 'wiki-codehike-watch', enforce: 'pre', generateBundle(_options, bundle) { for (const file of Object.values(bundle)) { if (file.type === 'chunk' && Object.keys(file.modules).some(id => /node_modules\/(react|react-dom|codehike|@code-hike)\//.test(id))) throw new Error('Build-only Code Hike/React leaked into a runtime bundle') } }, async handleHotUpdate(ctx) { if (ctx.file.endsWith('.md')) await codeCache.refresh() } }] },
  markdown: {
    highlight: (code, lang) => codeCache.get(code, lang).html,
    config: md => { wikiMarkdown(md, codeCache); addTopicContext(md, posts) },
    codeCopyButtonTitle: '复制代码',
    lineNumbers: true,
    theme: { light: 'github-light', dark: 'github-dark' },
    container: { tipLabel: '提示', warningLabel: '注意', dangerLabel: '风险', infoLabel: '说明', detailsLabel: '展开细节' }
  },
  themeConfig: {
    logo: '/favicon.svg', siteTitle: site.title,
    nav: [
      {text:'知识目录',link:'/knowledge/'},
      {text:'学习路线',link:'/paths/'},
      {text:'场景与排障',link:'/cases/'},
      {text:'资源',items:[{text:'源码阅读',link:'/resources/source-reading.html'},{text:'实验与验证',link:'/resources/experiments.html'},{text:'复习与推理',link:'/resources/review.html'},{text:'主题筛选',link:'/tags.html'}]},
      {text:'关于',link:'/about.html'}
    ],
    editLink: { pattern: `${site.repoUrl}/edit/main/docs/:path`, text:'在 GitHub 编辑此页' },
    sidebar,
    socialLinks: [{ icon: 'github', link: site.repoUrl, ariaLabel: '查看 GitHub 源码' }],
    outline: { level: [2, 3], label: '本文目录' },
    docFooter: { prev: '分类前一项', next: '分类后一项' },
    lastUpdated: { text: '更新于', formatOptions: { dateStyle: 'medium' } },
    darkModeSwitchLabel: '主题', lightModeSwitchTitle: '切换到浅色模式', darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '知识目录', returnToTopLabel: '回到顶部', skipToContentLabel: '跳转到正文',
    notFound: { code: '404', title: '这页暂时找不到', quote: '链接可能已经移动。可以回到首页，或用搜索找找关键词。', linkLabel: '回到首页', linkText: '回到首页' },
    footer: { message: '基于 VitePress 构建', copyright: site.title },
    search: {
      provider: 'local',
      options: {
        detailedView: true,
        _render: renderSearch,
        miniSearch: { options: { tokenize: tokenizeChinese }, searchOptions: { prefix: true, fuzzy: false, combineWith: 'AND' } },
        translations: {
          button: { buttonText: '搜索知识库', buttonAriaLabel: '搜索知识库' },
          modal: {
            displayDetails: '显示详细结果', resetButtonTitle: '清空搜索', backButtonTitle: '关闭搜索', noResultsText: '没有找到已发布内容，可换用技术名或到知识目录查看规划',
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
