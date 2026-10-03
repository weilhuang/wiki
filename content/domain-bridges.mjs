export const domainBridges = {
  java:'[安全发布](/knowledge/java/juc-foundations/jmm-safe-publication.html)与[任务接纳](/knowledge/java/juc-execution/executor-admission.html)解释本进程交接状态与工作；[线程证据](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)再帮助定位执行与等待。进入[Spring 容器](/knowledge/frameworks/spring-container/)时，继续追踪谁创建和持有这些对象。需要解释资源等待，转到[连接预算](/knowledge/frameworks/data-access/connection-budget.html)，不能用集合线程安全代替外部资源合同。',
  go:'[channel 同步与交接](/knowledge/go/concurrency/channel-memory-ownership.html)解释本地可见性和对象访问责任，可与[Java 安全发布](/knowledge/java/juc-foundations/jmm-safe-publication.html)对照。[运行时证据](/knowledge/go/runtime/scheduler-netpoll-diagnosis.html)把实际等待接回[操作系统视角](/knowledge/foundations/operating-systems/blocking-waiting.html)。[context 取消](/knowledge/go/concurrency/context-cancellation.html)只能解释信号和工作；写入结果未知时，继续进入[业务幂等](/knowledge/distributed/reliable-interactions/idempotency.html)。[进程停机](/knowledge/go/lifecycle/graceful-shutdown.html)定义本机责任，平台侧继续读[就绪与排空](/knowledge/cloud/lifecycle/readiness-draining.html)，来源复核与顺序模型不冒充集群运行。',
  frameworks:'[条件装配](/knowledge/frameworks/spring-boot/conditional-configuration.html)决定哪些定义进入容器，[AOP 分派](/knowledge/frameworks/spring-aop/proxy-dispatch.html)决定经代理的一次调用怎样进入目标。[事务代理](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)解释哪条连接参与提交；[库存不变量](/knowledge/data/transactions/inventory-invariants.html)再检查数据库里的业务承诺。[连接预算](/knowledge/frameworks/data-access/connection-budget.html)则把框架范围接到[等待排障](/troubleshooting/connection-waiting.html)。',
  data:'[索引访问路径](/knowledge/data/indexes/composite-index-access-paths.html)解释怎样找到候选，[MVCC 读取边界](/knowledge/data/transactions/mvcc-read-views.html)解释能看到哪个版本。本地事实提交后，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存跨组件交接责任；[缓存新鲜度](/knowledge/data/cache/invalidation-freshness.html)解释读取为何仍会落后。最终用[联合恢复](/cases/orders/consistency-recovery.html)核对权威事实与派生结果。',
  distributed:'[幂等](/knowledge/distributed/reliable-interactions/idempotency.html)把重复尝试接回本地裁决，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存待交接责任。[确认边界](/knowledge/distributed/messaging/delivery-ack-boundaries.html)继续区分保存、投递与消费提交；[租约与fencing](/knowledge/distributed/coordination/lease-fencing.html)解释接管之后旧工作如何被资源拒绝。目标对象还需经过[主体与租户授权](/knowledge/security/authorization/object-tenant-authorization.html)。',
  architecture:'先用[本地服务案例](/cases/orders/local-service-boundary.html)画出 HTTP、数据库和资源边界，再用[恢复案例](/cases/orders/consistency-recovery.html)检查跨组件责任。机制变成独立服务之后新增的网络与运维责任，需要明确成本，不能只画部署框。',
  cloud:'[服务事件与目标](/knowledge/cloud/observability/service-level-signals.html)先界定用户观察，再用[Go 运行时证据](/knowledge/go/runtime/scheduler-netpoll-diagnosis.html)或[连接等待](/troubleshooting/connection-waiting.html)排除局部原因。[就绪与排空](/knowledge/cloud/lifecycle/readiness-draining.html)把平台时序接回[应用停机](/knowledge/go/lifecycle/graceful-shutdown.html)；Kubernetes 来源复核和顺序模型仍需真实集群验证。恢复数据时，继续用[订单联合对账](/cases/orders/consistency-recovery.html)核对业务事实。',
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
  'spring-mechanisms.aop-run':'Spring 机制实验：代理接收者、条件装配与退让',
  'mysql-mechanisms.real-run':'MySQL 机制实验：索引访问路径与多会话读视图',
  'messaging.protocol-run':'消息与协调模型：确认、重投、毒消息与旧持有者',
  'go-runtime.channel-run':'Go 运行时实验：channel 交接、CPU、网络等待与有界堆积',
  'cloud.models-run':'可靠性模型：事件统计、服务预算与排空时序',
  'spring-definition.execution':'BeanDefinition 定位、注册与创建实验'
}
