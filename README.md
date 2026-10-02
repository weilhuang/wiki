# 工程札记

基于 VitePress 的中文后端工程知识站。按先修关系组织 Spring 服务边界、Go 服务生命周期和数据一致性三条学习路径，章节从具体问题进入机制、反例与综合评审。

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

## 内容结构与发布门禁

- `curriculum.mjs`：主题、路径、章节顺序、阶段、先修关系、兼容路由与证据引用的唯一结构来源
- `docs/learn/<path-id>/index.md`：完整路径导读；同目录其他 Markdown 是稳定章节路由
- `docs/guide/`：知识地图、实验与评审、明确标注的后续范围
- `evidence/*.json`：基础实验的执行范围、命令、退出码、版本和下载 ZIP 的 SHA256
- `docs/.vitepress/theme/`：默认主题扩展，仅包含关键词索引、Mermaid 与代码分步组件
- `site.config.mjs`：站点名称、仓库、域名和部署子路径
- `scripts/`、`tests/`：课程结构、证据、搜索、代码/图和输出验证

首批发布合同是三条路径各五章及三份导读。`npm run docs:build` 会拒绝缺章、未登记章节、草稿、先修环、缺失指南、未通过的基础实验及 ZIP 哈希不匹配。内容 `ready` 与实验 `verified` 是两种独立状态；实验通过仍需内容和平台独立评审，不能自动替代发布审阅。

开发服务器可用于本地预览已集成的正文；缺章时不制造占位页，也不能把本地预览当作完整发布。草稿留在 `docs/` 之外，避免构建到公开站点。新增章节或调整 manifest 后重启开发服务器，同步侧栏与内容索引。

每章 frontmatter 是标题、摘要、日期、标签、目标与版本的唯一内容来源，保留一个一级标题：

```yaml
---
title: 本章标题
description: 本章解决的问题与结论范围。
date: "2026-10-02"
updated: "2026-10-02"
tags: [Go, 并发]
objectives: [证明启动的任务都会被等待和收尾, 明确并发上限与失败结果合同]
versions: ["Go 1.27.1"]
---
```

章号、分组、先修 ID 和前后章由 manifest 决定；日期不影响学习顺序。站内链接使用 `/learn/<path-id>/<chapter-slug>`，不要手写部署子目录。Vue 中使用 VitePress `withBase`。默认保留 `.html`，导读使用目录 URL，以适配 GitHub Pages。

旧 `/blog/` 与两篇既有文章地址在构建后生成兼容 HTML：跳转保留 query/hash，使用 `location.replace` 避免 Back 循环；有 canonical、noindex 与无 JavaScript 的逐节链接。它们不进入搜索、RSS 或 sitemap。这是静态 HTML 兼容跳转，不是 HTTP 301。旧章节锚点与实验 ZIP 路径继续受检查。

RSS 保留给已有订阅者，标签提供横切索引；它们都从同一已登记 canonical 章节清单投影。主导航按路径组织。代码复制、行号、代码组、提示块保留 VitePress 原生行为，没有第三方统计、评论或远程搜索。

### Code Hike

所有普通代码围栏在构建时调用 **Code Hike 1.1.0** 的官方 `highlight` API，保留 token 与注释范围。它原生面向 React/MDX，本项目使用独立的 VitePress 适配层，不声称支持完整 React 组件或全部 Code Hike 注释处理器。React 18.3.1 仅用于构建期模块解析；构建检查会阻止 React、React DOM、Code Hike 进入客户端 bundle。

支持 `focus`、`mark`、`step`；未知注释会使构建失败。分步代码围栏写为 `java steps` 等，在源码中使用官方形式 `// !step(1:3) 这几行的解释`。范围相对于注释后清理过的代码，从 1 开始并包含终点。每个分步区保留完整代码、原生复制按钮、可键盘操作的步骤按钮与可展开的全部解释。复制内容不含讲解注释。

开发时修改现有 Markdown 会重新编译代码缓存；新增章节后应重启开发服务器，以同步导航。暂不接受 `<<<` 隐式代码导入，避免缓存与实际展示的源码不一致。

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
