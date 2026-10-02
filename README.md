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

界面使用 VitePress 原生默认主题，不做首页营销布局或全局视觉覆盖。项目固定 VitePress 1.6.4 稳定版，使用锁文件安装依赖。Vite 6.4.3 override 避免继续使用 VitePress 1.x 默认的旧 Vite 5，构建和本地搜索已列入验证范围。升级时请一起检查 `package-lock.json`、生产构建和浏览器交互，不要直接切换到 `@next`。

## 内容结构

- `docs/guide/knowledge-map.md`：知识地图、先修关系、阅读顺序
- `docs/blog/*.md`：完整文章；列表、标签和侧栏从 frontmatter 自动生成
- `docs/.vitepress/theme/`：默认主题扩展，仅包含标签索引、Mermaid 与代码分步组件
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

代码复制、行号、代码组、提示块保留 VitePress 原生行为。没有第三方统计、评论或远程搜索。

### Code Hike

所有普通代码围栏在构建时调用 **Code Hike 1.1.0** 的官方 `highlight` API，保留 token 与注释范围。它原生面向 React/MDX，本项目使用独立的 VitePress 适配层，不声称支持完整 React 组件或全部 Code Hike 注释处理器。React 18.3.1 仅用于构建期模块解析；构建检查会阻止 React、React DOM、Code Hike 进入客户端 bundle。

支持 `focus`、`mark`、`step`；未知注释会使构建失败。分步代码围栏写为 `java steps` 等，在源码中使用官方形式 `// !step(1:3) 这几行的解释`。范围相对于注释后清理过的代码，从 1 开始并包含终点。每个分步区保留完整代码、原生复制按钮、可键盘操作的步骤按钮与可展开的全部解释。复制内容不含讲解注释。

开发时修改现有 Markdown 会重新编译代码缓存；新增文章后应重启开发服务器，以同步导航。暂不接受 `<<<` 隐式代码导入，避免缓存与实际展示的源码不一致。

### Mermaid

使用 **Mermaid 11.17.2** 官方渲染器，通过本项目的轻量 Markdown fence 适配。使用标准 `mermaid` 围栏，必须包含 `accTitle:` 与 `accDescr:`。流程判断使用 `D("判断"):::decision`，保持圆角虚线矩形。统一配色、灰色连线和 SVG 边标签接近参考图；无需将图源上传到任何图形服务。

Mermaid 在浏览器中按需生成 SVG，JavaScript 被禁用时保留文字说明和图源，不会生成图形。始终使用 strict 安全模式和 SVG 文本标签，不允许图内覆盖初始化、安全选项、点击动作或嵌入 HTML。白底画布在明暗主题中保持对比度，宽图在自身容器中横向滚动。

`npm test` 会检查文章中的全部 Mermaid 语法、Code Hike 干净源码和步骤范围；语法验证不等于视觉验证，部署后仍需检查实际 SVG 和移动布局。

### 可运行实验

Spring 章节提供仅源码的 ZIP，在 `docs/public/examples/`。正文标明 JDK、Gradle 与依赖版本；示例实验与课程仓库相互独立。

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
