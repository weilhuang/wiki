// Structure lives here; chapter prose and metadata live only in Markdown.
const pathDefinitions = [
  {
    id: 'spring-service-boundaries', themeId: 'application-frameworks', relatedThemeIds: ['data-storage', 'engineering'],
    title: 'Spring 服务边界', description: '从容器对象走到 HTTP、事务与连接资源，交付能用失败矩阵评审的订单服务。',
    prerequisites: ['Java 对象与异常', 'HTTP 请求响应', 'SQL 提交与回滚'],
    outcomes: ['资源所有权图', 'HTTP 与数据库失败矩阵', '连接预算与服务边界 ADR'],
    slugs: ['bean-ownership-lifecycle', 'mvc-request-completion', 'transaction-proxy', 'connection-budget-timeouts', 'service-boundary-review']
  },
  {
    id: 'go-service-lifecycle', themeId: 'runtime-concurrency', relatedThemeIds: ['distributed-systems', 'cloud-delivery'],
    title: 'Go 服务生命周期', description: '沿请求、协程、下游调用和停机追踪责任，让启动的工作和占用的资源都有收尾证据。',
    prerequisites: ['Go 函数、error 与 defer', 'channel 与 goroutine', 'HTTP 请求响应'],
    outcomes: ['入口与响应合同', '有界并发及调用预算', '进程停机证据与运行手册'],
    slugs: ['http-request-contract', 'context-cancellation', 'bounded-concurrency-ownership', 'http-client-budgets', 'graceful-shutdown-review']
  },
  {
    id: 'data-consistency', themeId: 'data-storage', relatedThemeIds: ['messaging-events', 'distributed-systems', 'engineering'],
    title: '数据一致性', description: '先写订单和库存的不变量，再处理未知结果、事件交接、缓存陈旧与恢复对账。',
    prerequisites: ['SQL 与唯一约束', '事务提交和回滚', '两个请求交错执行'],
    outcomes: ['并发不变量及反例', '幂等、事件与缓存合同', '恢复对账查询和演练报告'],
    slugs: ['invariants-isolation-locks', 'idempotency-unknown-outcomes', 'outbox-consumer-dedup', 'cache-freshness-invalidation', 'consistency-recovery-review']
  }
]
const prefixes = { 'spring-service-boundaries': 'spring', 'go-service-lifecycle': 'go', 'data-consistency': 'data' }
const existing = { 'transaction-proxy': 'spring-transaction-proxy', 'context-cancellation': 'go-context-cancellation' }
export const curriculum = {
  batch: { id: 'foundations-2026-10', expectedPaths: 3, chaptersPerPath: 5 },
  themes: [
    ['runtime-concurrency', '运行时与并发', 'active'], ['application-frameworks', '应用框架与服务边界', 'active'],
    ['data-storage', '数据存储与一致性', 'active'], ['messaging-events', '消息与事件系统', 'roadmap'],
    ['distributed-systems', '分布式系统', 'roadmap'], ['cloud-delivery', '云原生与交付', 'roadmap'],
    ['observability-performance', '可观测性与性能', 'roadmap'], ['identity-security', '身份与安全', 'roadmap'],
    ['engineering', '架构与工程方法', 'roadmap']
  ].map(([id, title, status]) => ({ id, title, status })),
  requiredPages: ['index.md', 'learn/index.md', 'guide/knowledge-map.md', 'guide/practice.md', 'guide/roadmap.md', 'tags.md', 'about.md'],
  paths: pathDefinitions.map(({ slugs, ...path }) => ({
    ...path, introSource: `learn/${path.id}/index.md`,
    stages: [
      { title: '理解边界', chapters: slugs.slice(0, 2).map(s => `${prefixes[path.id]}-${s}`) },
      { title: '验证与诊断', chapters: slugs.slice(2, 4).map(s => `${prefixes[path.id]}-${s}`) },
      { title: '综合评审', chapters: slugs.slice(4).map(s => `${prefixes[path.id]}-${s}`) }
    ]
  })),
  chapters: pathDefinitions.flatMap(path => path.slugs.map((slug, index) => ({
    id: `${prefixes[path.id]}-${slug}`, pathId: path.id, source: `learn/${path.id}/${slug}.md`, order: index + 1,
    prerequisites: index ? [`${prefixes[path.id]}-${path.slugs[index - 1]}`] : [],
    aliases: existing[slug] ? [`/blog/${existing[slug]}.html`] : [],
    contentStatus: 'ready',
    practice: `/examples/${existing[slug] || path.id}.zip`,
    evidence: `evidence/${existing[slug] || path.id}.json`
  }))),
  aliases: [{ from: '/blog/', to: '/learn/' }]
}
