// Stable topic identity is independent of learning-route membership.
export const migrations = [
  ['spring-service-boundaries','bean-ownership-lifecycle','frameworks.bean-lifecycle','knowledge/frameworks/spring-container/bean-lifecycle.md','frameworks','spring-container','concept'],
  ['spring-service-boundaries','mvc-request-completion','frameworks.mvc-pipeline','knowledge/frameworks/spring-mvc/request-pipeline.md','frameworks','spring-mvc','source'],
  ['spring-service-boundaries','transaction-proxy','frameworks.transaction-proxy','knowledge/frameworks/spring-transactions/proxy-call-chain.md','frameworks','spring-transactions','source'],
  ['spring-service-boundaries','connection-budget-timeouts','frameworks.connection-budget','knowledge/frameworks/data-access/connection-budget.md','frameworks','data-access','concept'],
  ['spring-service-boundaries','service-boundary-review','architecture.local-service-boundary','cases/orders/local-service-boundary.md','architecture','business-cases','scenario'],
  ['go-service-lifecycle','http-request-contract','go.http-contract','knowledge/go/http/request-response-contract.md','go','http','concept'],
  ['go-service-lifecycle','context-cancellation','go.context-cancellation','knowledge/go/concurrency/context-cancellation.md','go','concurrency','source'],
  ['go-service-lifecycle','bounded-concurrency-ownership','go.bounded-work','knowledge/go/concurrency/bounded-work.md','go','concurrency','concept'],
  ['go-service-lifecycle','http-client-budgets','go.client-budgets','knowledge/go/http/client-budgets.md','go','http','concept'],
  ['go-service-lifecycle','graceful-shutdown-review','go.graceful-shutdown','knowledge/go/lifecycle/graceful-shutdown.md','go','lifecycle','scenario'],
  ['data-consistency','invariants-isolation-locks','data.inventory-invariants','knowledge/data/transactions/inventory-invariants.md','data','transactions','concept'],
  ['data-consistency','idempotency-unknown-outcomes','distributed.idempotency','knowledge/distributed/reliable-interactions/idempotency.md','distributed','reliable-interactions','concept'],
  ['data-consistency','outbox-consumer-dedup','distributed.transactional-outbox','knowledge/distributed/events/transactional-outbox.md','distributed','events','pattern'],
  ['data-consistency','cache-freshness-invalidation','data.cache-invalidation','knowledge/data/cache/invalidation-freshness.md','data','cache','pattern'],
  ['data-consistency','consistency-recovery-review','architecture.consistency-recovery','cases/orders/consistency-recovery.md','architecture','business-cases','scenario']
].map(([pathId,slug,id,source,domain,category,kind])=>({pathId,slug,id,source,domain,category,kind,oldSource:`learn/${pathId}/${slug}.md`,legacyId:`${pathId.startsWith('spring')?'spring':pathId.startsWith('go')?'go':'data'}-${slug}`}))
