# 工程札记

基于 VitePress 的中文知识库与博客。文章按主题组织，从具体问题进入机制、验证方法和适用边界。

## 本地运行

使用 `.nvmrc` 中固定的 Node 24.19.0（npm 11.9.0）。

```sh
npm ci
npm run docs:dev
```

```sh
npm run check        # 单元测试、内容检查、静态构建、站内链接检查
npm run docs:preview # 预览生产产物，在 /wiki/ 路径打开
```

项目固定 VitePress 1.6.4 稳定版，使用锁文件安装依赖。Vite 6.4.3 override 避免继续使用 VitePress 1.x 默认的旧 Vite 5，构建和本地搜索已列入验证范围。升级时请一起检查 `package-lock.json`、生产构建和浏览器交互，不要直接切换到 `@next`。

## 内容结构

- `docs/guide/knowledge-map.md`：知识地图、先修关系、阅读顺序
- `docs/blog/*.md`：完整文章；列表、标签和侧栏从 frontmatter 自动生成
- `docs/.vitepress/theme/`：页面组件和阅读主题
- `site.config.mjs`：站点名称、仓库、域名和部署子路径
- `scripts/`、`tests/`：元数据、RSS、本地分词及构建检查

新文章需要以下元数据，并保留一个一级标题。日期必须加引号。

```yaml
---
title: 文章标题
description: 用一两句话说清楚这篇文章解决什么问题。
date: "2026-10-02"
category: Go
tags: [Go, 并发]
order: 10
---
```

草稿请放在 `docs/` 之外。静态站点中的文件都可能被公开访问，仅仅不放进导航并不能隐藏它们。构建会拒绝含 `draft: true` 的博客文章。

站内 Markdown 链接使用 `/blog/article-slug` 或 `/guide/knowledge-map`，不要手写部署目录。Vue 组件中的链接使用 VitePress 的 `withBase`。默认保留 `.html` 后缀，以适配 GitHub Pages 的静态路由。

代码复制、行号、代码组、提示块由 VitePress 原生支持。没有引入评论、统计、外部字体或远程搜索。暂未引入额外数学/图表插件；需要时应先加入实际内容，再验证渲染和可访问性。

## GitHub Pages

仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。工作流只使用标准 GitHub 托管 Linux runner。

- PR：只读检查与构建，不发布
- `main`：检查通过后部署 GitHub Pages
- 部署权限仅授予 `deploy` job；安装和构建不持有 Pages 写入权限
- Actions 固定到完整 commit SHA，不保存 checkout 凭据，不使用 `pull_request_target`

生产目录是 `docs/.vitepress/dist`。包括 RSS、sitemap、404 页面和 `.nojekyll`。站点的公开地址由 `site.config.mjs` 决定。

## 迁移到新仓库

1. 修改 `site.config.mjs` 中的 `repository`、`origin` 和 `base`。项目站点通常使用 `/<repo>/`；账号根站点使用 `/`。
2. 更新本 README 的预览路径说明，以及必要的品牌文字。站内链接、搜索结果、RSS、canonical 和 sitemap 会使用新配置。
3. 在新仓库启用 GitHub Actions Pages，运行 `npm ci && npm run check`，再检查实际部署后的深层链接和搜索。
4. 如需新仓库没有旧历史，应从审阅后的文件创建全新的 Git 历史，而不是推送旧 `.git`。保留需要的来源与许可证声明。

修改仓库可见性不会收回已经公开的副本，也不保证旧公开链接中的内容消失。GitHub Pages 对私有仓库的可用性受账号计划限制；迁移或设为私有前请核对账号当前规则。

## 内容约定

写清楚前提、机制、失败路径与参考资料。示例不是生产部署模板，不虚构个人履历或生产事故。引用原文、示例代码或图表时保留原始来源及必要的许可证信息。
