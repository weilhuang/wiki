export const domainBridges = {
  java:'对象和集合机制决定本进程如何保存状态；进入[Spring 容器](/knowledge/frameworks/spring-container/)时，继续追踪谁创建和持有这些对象。需要解释资源等待，转到[连接预算](/knowledge/frameworks/data-access/connection-budget.html)，不能用集合线程安全代替外部资源合同。',
  go:'[context 取消](/knowledge/go/concurrency/context-cancellation.html)只能解释信号和工作；写入结果未知时，继续进入[业务幂等](/knowledge/distributed/reliable-interactions/idempotency.html)。[进程停机](/knowledge/go/lifecycle/graceful-shutdown.html)定义本机责任，平台摘流与集群行为仍在云原生领域另行建立。',
  frameworks:'[事务代理](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)解释哪条连接参与提交；[库存不变量](/knowledge/data/transactions/inventory-invariants.html)再检查数据库里的业务承诺。[连接预算](/knowledge/frameworks/data-access/connection-budget.html)则把框架范围接到[等待排障](/troubleshooting/connection-waiting.html)。',
  data:'本地事实提交后，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存跨组件交接责任；[缓存新鲜度](/knowledge/data/cache/invalidation-freshness.html)解释读取为何仍会落后。最终用[联合恢复](/cases/orders/consistency-recovery.html)核对权威事实与派生结果。',
  distributed:'[幂等](/knowledge/distributed/reliable-interactions/idempotency.html)把重复尝试接回一份本地裁决；[Outbox](/knowledge/distributed/events/transactional-outbox.html)把提交后的责任交给另一参与者。是否值得引入这条边界，应回到[架构领域](/knowledge/architecture/)的约束与替代方案。',
  architecture:'先用[本地服务案例](/cases/orders/local-service-boundary.html)画出 HTTP、数据库和资源边界，再用[恢复案例](/cases/orders/consistency-recovery.html)检查跨组件责任。机制变成独立服务之后新增的网络与运维责任，需要明确成本，不能只画部署框。',
  cloud:'从[Go 进程停机](/knowledge/go/lifecycle/graceful-shutdown.html)理解所有权，再到[连接等待排障](/troubleshooting/connection-waiting.html)练习假设与证据；这些结果不会自动成为集群保证。恢复数据时回到[订单联合对账](/cases/orders/consistency-recovery.html)，服务存活只是一个信号。',
  security:'在[订单服务边界](/cases/orders/local-service-boundary.html)中先识别尚未实现的身份与授权责任；不把教学接口当作安全系统。认证与授权是不同问题，未来 RBAC 与对象级授权会归入本领域。错误响应与日志的公开内容还要与[HTTP 合同](/knowledge/go/http/request-response-contract.html)配合。',
  foundations:'在[实验与验证](/resources/experiments.html)比较资料、源码、静态、进程和真实服务证据；从一个错误实现是否会被断言抓住，开始学习测试区分力。随后在[复习与推理](/resources/review.html)改变条件，检查模型是否能够解释新结果。'
}
export const experimentTitles = {
  'legacy.spring-service-boundaries':'Spring 服务边界实验：容器、MVC 与连接',
  'legacy.spring-transaction-proxy':'Spring 事务代理实验',
  'legacy.go-service-lifecycle':'Go 服务生命周期实验：HTTP、工作池、调用与停机',
  'legacy.go-context-cancellation':'Go context 时序实验',
  'legacy.data-consistency':'订单数据一致性实验：库存、幂等、事件、缓存与恢复',
  'spring-definition.execution':'BeanDefinition 定位、注册与创建实验'
}
