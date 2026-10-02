# 工程札记

基于 VitePress 的中文后端工程知识站。按大领域、分类与稳定知识点组织；路线、源码、实验和复习视图引用同一正文。文章从具体问题进入机制、源码、条件与取舍。

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

## 内容模型与发布门禁

- `content/taxonomy.mjs`：九个稳定领域、分类及规划范围；`domain-guides.mjs` / `category-guides.mjs` 保存对应教学导读
- `docs/knowledge/<domain>/<category>/`：拥有稳定 ID 的 canonical 知识正文；案例、排障页可使用独立任务路由，主分类仍明确
- `content/paths.mjs`：路线只引用知识 ID，说明准入、阅读目的与阶段任务，不复制正文或推导强先修
- `content/sources/`、`content/verification/`：来源和多维验证台账；五组历史 `evidence/*.json` 与 ZIP 保留原身份
- `content/redirects.json`：原 blog/learn 直接到最终 canonical，支持必要的逐锚点迁移
- `content/review-questions.json`、`content/search-intents.json`：复习问题回链主文，实际搜索问法定位到具体小节
- `scripts/generate-views.mjs`：从同一元数据生成目录、路线与资源页；生成页标记 `generated: true`，应修改其来源而非生成结果
- `site.config.mjs`：站名、仓库、域名与部署子路径；`docs/.vitepress/theme/` 保留默认主题及内容增强组件

知识正文必填稳定 `id`、`kind`、`status`、`title`、`description`、`domain`、`category`、日期及适用 `scope`。文章类型为 concept/source/pattern/scenario/troubleshooting/lab/review；编辑状态为 planned/draft/review/published/retired。只有 published 正文进入公开 docs，其他状态留在 docs 外。标签按 technology/mechanism/task/scenario 使用受控 ID。

requires、recommendedBefore、related、contrastsWith 等关系都带目标 ID 与 reason。只有 requires 必须无环；推荐顺序不自动成为先修。知识没有唯一 pathId，也没有全站 3×5 数量约束。必要基础可用文字补充，不为没有写完的先修制造空链接。

验证记录独立表示 source-reviewed/static-checked/executed，以及 not-run/pass/fail/blocked/stale。概念与模式页无需伪造实验 ZIP；声称 executed/pass 时必须给出绑定源码与真实成功命令，文件变化使旧记录失效。新实验版本使用新身份，不覆盖历史包。资料复核、语法通过与运行结果不能互相冒认。

`npm run check` 会生成视图并校验元数据、关系、别名、适用证据、源码/ZIP身份、代码/图、实际搜索库存与构建输出。当前重构批次另设三类内容样板准入，这属于一次发布范围，不是永久限制文章形状。所有标题和顺序来源分工明确；新增分类或修改结构后重启开发服务器以刷新导航。

正文保留一个 H1。站内 Markdown 链接使用不带部署 base 的完整 `.html` canonical 地址；Vue 使用 VitePress `withBase`。目录页使用尾斜线。不要从标题或文章顺序生成路由。

旧 URL 构建为 noindex 的静态兼容页，保留 query/hash、无脚本逐节入口，并使用 location.replace 避免 Back 循环；不是 HTTP 301。搜索、RSS 和 sitemap 不收迁移壳。默认搜索扩展仅用 VitePress 支持的本地渲染接口，不上传查询或图源。

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
