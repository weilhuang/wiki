export const domainBridges = {
  java:'[安全发布](/knowledge/java/juc-foundations/jmm-safe-publication.html)与[任务接纳](/knowledge/java/juc-execution/executor-admission.html)解释本进程交接状态与工作；[线程证据](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)再帮助定位执行与等待。进入[Spring 容器](/knowledge/frameworks/spring-container/)时，继续追踪谁创建和持有这些对象。需要解释资源等待，转到[连接预算](/knowledge/frameworks/data-access/connection-budget.html)，不能用集合线程安全代替外部资源合同。',
  go:'[context 取消](/knowledge/go/concurrency/context-cancellation.html)只能解释信号和工作；写入结果未知时，继续进入[业务幂等](/knowledge/distributed/reliable-interactions/idempotency.html)。[进程停机](/knowledge/go/lifecycle/graceful-shutdown.html)定义本机责任，平台摘流与集群行为仍在云原生领域另行建立。',
  frameworks:'[事务代理](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)解释哪条连接参与提交；[库存不变量](/knowledge/data/transactions/inventory-invariants.html)再检查数据库里的业务承诺。[连接预算](/knowledge/frameworks/data-access/connection-budget.html)则把框架范围接到[等待排障](/troubleshooting/connection-waiting.html)。',
  data:'本地事实提交后，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存跨组件交接责任；[缓存新鲜度](/knowledge/data/cache/invalidation-freshness.html)解释读取为何仍会落后。最终用[联合恢复](/cases/orders/consistency-recovery.html)核对权威事实与派生结果。',
  distributed:'[幂等](/knowledge/distributed/reliable-interactions/idempotency.html)把重复尝试接回一份本地裁决；[Outbox](/knowledge/distributed/events/transactional-outbox.html)把提交后的责任交给另一参与者。是否值得引入这条边界，应回到[架构领域](/knowledge/architecture/)的约束与替代方案。',
  architecture:'先用[本地服务案例](/cases/orders/local-service-boundary.html)画出 HTTP、数据库和资源边界，再用[恢复案例](/cases/orders/consistency-recovery.html)检查跨组件责任。机制变成独立服务之后新增的网络与运维责任，需要明确成本，不能只画部署框。',
  cloud:'从[Go 进程停机](/knowledge/go/lifecycle/graceful-shutdown.html)理解所有权，再到[连接等待排障](/troubleshooting/connection-waiting.html)练习假设与证据；这些结果不会自动成为集群保证。恢复数据时回到[订单联合对账](/cases/orders/consistency-recovery.html)，服务存活只是一个信号。',
  security:'[会话与令牌](/knowledge/security/authentication/authentication-boundaries.html)确定哪些身份声明可以信任；[对象授权](/knowledge/security/authorization/object-tenant-authorization.html)再将主体与当前订单事实联系起来。提交前权限发生变化时，需要与[库存不变量](/knowledge/data/transactions/inventory-invariants.html)中的并发裁决一起思考。错误响应与日志还要遵守[HTTP 响应边界](/knowledge/go/http/request-response-contract.html)。',
  foundations:'从[请求在等什么](/knowledge/foundations/operating-systems/blocking-waiting.html)进入[连接预算](/knowledge/frameworks/data-access/connection-budget.html)，把等待条件接回真实资源持有者；从[反例与断言](/knowledge/foundations/testing/assertion-counterexamples.html)进入[对象授权](/knowledge/security/authorization/object-tenant-authorization.html)，检查一个错误的允许是否会被精确拒绝。两类实验的观察范围不同，不能将内存模型当作数据库或操作系统保证。'
}
export const experimentTitles = {
  'legacy.spring-service-boundaries':'Spring 服务边界实验：容器、MVC 与连接',
  'legacy.spring-transaction-proxy':'Spring 事务代理实验',
  'legacy.go-service-lifecycle':'Go 服务生命周期实验：HTTP、工作池、调用与停机',
  'legacy.go-context-cancellation':'Go context 时序实验',
  'legacy.data-consistency':'订单数据一致性实验：库存、幂等、事件、缓存与恢复',
  'foundations-service-lab':'等待条件与断言实验：线程、TCP loopback 和受控交错',
  'security-boundaries':'身份与对象授权模型：撤销、租户、动作和提交版本',
  'java-service-mechanisms':'Java 机制实验：安全发布、任务接纳与线程诊断',
  'spring-definition.execution':'BeanDefinition 定位、注册与创建实验'
}
