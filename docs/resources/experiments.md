---
title: 实验与验证
description: 完整实验源、验证范围和可追溯版本，独立于文章编辑状态。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 实验与验证

实验用来区分两个解释：先预测，再安排时序、观察业务结果，最后改变一项条件。没有实验包的概念页也可以通过资料与源码复核；有运行记录的文章也不能据此宣称生产可靠。

## 验证分别回答什么

| 记录 | 支持的问题 | 不能自动推出 |
| --- | --- | --- |
| 资料与源码复核 | 合同、实现分支与版本 | 本机或生产已运行 |
| 静态检查 | 语法、引用、图、片段一致性 | 业务执行结果 |
| 进程内或单元运行 | 控制输入下的状态变化 | 真实依赖全部行为 |
| 真实服务/进程运行 | 指定版本与故障模型下的观察 | 多节点、容量或生产保证 |

每份记录另有未运行、通过、失败、受阻或过期状态。源码或参数变化后，需要重判旧证据是否仍适用；纯链接修改不伪装成一次新实验。

## 可下载的完整实验

### 订单模块演进的顺序协议模型 {#experiment-architecture-order-extraction-model}

[下载完整模型](/examples/order-extraction-protocol-model.py) · [查看运行结果](/examples/order-extraction-model-results.txt)。历史运行范围：R2，Python 3.12.14，标准库，单进程顺序内存模型；原13测试入口加强固定业务事实、停写期拒绝与历史版本指纹等断言，13项通过。

关联知识：[订单模块要不要拆成服务：从不拆的理由到可回退的迁移](/cases/architecture/order-service-extraction.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- SHA256：2609ab904fd4f0b6d963fd91d662399b45c1dad6c3f251e914f2ab0d3839050d
- SHA256：62326aca5e0cf6bd030dae3ad2b70a972296ecfb239feabd72d75b815e0dd9cf
- 未覆盖：无数据库/HTTP服务/broker/集群/网络/真实崩溃；原子性是假设，不证明生产栅栏协议可实现；无库存Saga与取消墓碑执行测试；依赖夹具不扫描生产源码；耗时不用于性能结论；历史版本指纹仅覆盖本进程已见且保留的已定义语义字段，无持久化/清理策略，不证明未见权威历史
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### 等待条件与断言实验：线程、TCP loopback 和受控交错 {#experiment-foundations-service-lab}

[查看运行结果](/examples/foundations-service-results.json) · [下载源码包](/examples/foundations-service-lab.zip)。历史运行范围：CPython 3.12.14/Linux 固定计算、锁/空队列因果条件及真实TCP loopback；核对数据与线程/socket释放；两个事件控制交错，在computed和join后核对精确结果/副作用；同步观察done实际发布时的资源状态；五个原有坏实现命中精确预期原因列表；leak同时命中PUBLISH_ORDER与RESOURCE；真实启动失败必须精确匹配RuntimeError与injected startup failure，返回error/退出2且不得冒充业务负例；错误退出码、原因或缺字段不能假绿；额外启动身份源码变异由r2回归实际拒绝；r2三项真实service.py源变异：清理许可后提前发布done、中间结果错误后恢复、启动异常类型/消息替换；前两项分别命中PUBLISH_ORDER/RESULT且完成有界清理；第三项因精确启动归因不符拒绝，均非语法/启动失败冒充业务负例。

关联知识：[进程、线程与阻塞 I/O：请求在等什么](/knowledge/foundations/operating-systems/blocking-waiting.html)、[用反例检验断言：结果、时序与失败归因](/knowledge/foundations/testing/assertion-counterexamples.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：CPython 3.12.14 / Linux，有限标准库与loopback实验；CPython 3.12.14 / Linux
- SHA256：483142b57f91b174429d717df532a8fdb15c01c836f84da9b062bb3bc244586e
- SHA256：98435b03a3dc98d10bffa5a7a0c3463238da202366b5cfc319b981e107bb8f9b
- 未覆盖：事件不能证明线程当时已进入内核睡眠；无远端网络/数据库/HTTP；时间数值只记录不设性能阈值；不证明调度公平性或生产容量；资源和回执为内存模型，不是真实服务；correct只代表指定正常路径，不包含生产异常恢复；不穷尽并发交错或证明无数据竞争；验证器保护有限，不是完整故障注入工具；启动异常作为基础设施异常记录，未冒认为目标业务反例；任务资源和effects是内存模型；不证明操作系统所有调度或真实数据库/HTTP行为；同步发布观察器只作用于本实验可控制的Event对象；不保证任意外部系统可获得同样观察面
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### HashMap JDK 21：API、实现观察与验证器回归 {#experiment-hashmap-jdk21}

[下载源码包](/examples/hashmap-jdk21-lab.zip)。历史运行范围：Temurin 21.0.12.1+1-LTS，7个公共API场景及完整调用示例；违约键的输出只属固定实现反例；同一验证命令中的4个显式可选实现观察：put第9节点、默认map第11节点、computeIfAbsent第8节点、树拆分6/7节点；逐键检查映射；5个可见错误假设分别由主异常首行指定 AssertionError 拒绝，验证器检查异常类型、对应命题消息和退出码1；整体exit0；R2验证器隔离回归：7个变异逐项要求退出1和具体目标故障证据；覆盖R1原三变异及命题/意外成功/compute映射丢失与污染。

关联知识：[HashMap 的查找、冲突与扩容](/knowledge/java/collections/hashmap.html)、[沿 OpenJDK 21 源码追踪 HashMap 的状态变化](/knowledge/java/collections/hashmap-source.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Temurin 21.0.12.1+1-LTS；OpenJDK jdk-21+35 source
- SHA256：02b804cadb81930fad375fd4cce3b08eddebdc60aebda1a7c620e2e6243d741d
- 未覆盖：不读取私有容量；位运算索引为独立模型，不能独自证明真实桶布局；不证明并发安全或性能；未执行GA二进制；仅通过Map.Entry实际类名观察Node/TreeNode；容量由固定源码推演，没有访问table字段；未测树高度/颜色/删除枚举；类型名不属于API保证；是反向命题检查，不是对JDK进行变异测试；最后一项验证独立位运算模型；变异仅作用于教学实验，不改JDK；不代表穷尽全部验证器漏洞
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### Java 并发与运行时实验：发布、线程池、线程与 GC 观察 {#experiment-java-service-mechanisms}

[下载源码包](/examples/java-service-mechanisms-lab.zip)。历史运行范围：One-shot volatile publication observed 42；Barrier-controlled split read-modify-write produced 1; AtomicInteger produced 2；All registered workers join; ChildFailures retains primary failure, appends distinct child causes, and deduplicates Throwable identity；A/B/C/D worker/queue/rejection and orderly shutdown exact-once task results；execute uncaught exception vs submit Future cause and afterExecute Throwable；shutdownNow returned exact pending Future wrapper; explicit cancellation; running task interrupt response；Controlled successful offer/shutdown/recheck/remove/reject race and termination；Ordinary worker failures and completed Future failures collected; expected execute exception isolated by exact type/message/count; all registered threads joined；Wrong volatile atomicity, max-first and drain-cancels claims fail with first exception line exactly java.lang.AssertionError and exact expected message；Compilation/startup or other exception types do not count as expected rejection；Two actual instrumented ThreadMXBean platform-thread snapshots with identity/state/full stack/monitor owner；Actual per-thread CPU time deltas and SerialGC log from bounded allocation；Four workers and watchdog joined; no child failure; complete final success marker and diagnostic process exit0；Independent-review-equivalent atomic and diagnostic source mutations fail after intended side effects with original cause and all threads joined；Ordinary executor late throw, wrong Future cause, and ordinary FutureTask error also fail with exact Caused by and cleanup; no circular-reference output；No surviving lab JVM after sequential mutations；ObservedPool proves cooperative release/shutdown/await does not invoke shutdownNow or interrupt the worker；A deliberately unreleased owned worker triggers the bounded three-second timeout, one force stop, ended worker and suppressed cleanup failure while preserving primary identity；Same Throwable emitted once, genuinely distinct children retained, and child already in primary cause graph not duplicated。

关联知识：[线程池如何接纳任务：线程、队列与拒绝](/knowledge/java/juc-execution/executor-admission.html)、[JMM 与安全发布：什么先于什么](/knowledge/java/juc-foundations/jmm-safe-publication.html)、[从线程与 GC 证据区分慢请求](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：OpenJDK jdk-21+35 source；Temurin 21.0.12.1+1-LTS execution；Temurin 21.0.12.1+1-LTS
- SHA256：b3d6db08e3ff95b35e5342c35bebba882ee1fdf72ae68c4ba99e0a900629184a
- 未覆盖：Execution is not proof of all JMM outcomes；No forced unsafe-publication reorder reproduction; no performance claim；Fixed platform-thread implementation; no capacity benchmark；No custom ThreadFactory failure or exhaustive policy/virtual-thread coverage；These refute named claims, not all incorrect executor/JMM implementations；Application-internal instrumentation, not successful external jcmd attach；No production request workload, virtual threads, JFR, heap-dump root analysis, or collector performance ranking；ActiveProcessorCount is a JVM setting, not an OS CPU quota; Xmx is not process RSS cap；Source mutation checks target ordinary child/Future error propagation, not every possible harness defect；Finite harness contract checks, not throughput or schedule stress tests
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### Spring 服务边界实验：容器、MVC 与连接 {#experiment-spring-service-boundaries}

[下载源码包](/examples/spring-service-boundaries.zip)。历史运行范围：4 组容器生命周期实验；5 组连接资源实验；8 个真实回环 HTTP 请求，同时核对业务副作用。

关联知识：[连接池与事务预算：请求卡住时，资源被谁占住](/knowledge/frameworks/data-access/connection-budget.html)、[容器创建与对象所有权：Bean 何时可用，谁负责关闭](/knowledge/frameworks/spring-container/bean-lifecycle.html)、[请求完成链：MVC 在哪里选择处理器、转换异常和提交响应](/knowledge/frameworks/spring-mvc/request-pipeline.html)、[订单服务评审：把对象、HTTP、事务和资源合同接起来](/cases/orders/local-service-boundary.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：jdk Temurin 21.0.12.1+1；gradle 8.10.2；springBoot 3.5.16；springFramework 6.2.19；tomcat 10.1.55；servlet 6.0；hikariCP 6.3.3；h2 2.3.232；hibernateValidator 8.0.3.Final；codeHike 1.1.0；mermaid 11.17.2
- SHA256：2b46b578290ea5f47544adcb08c53809c9cdecc6221684b45ef68a048eb30163
- 未覆盖：MySQL/PostgreSQL isolation/locks/driver cancellation；real downstream HTTP timing/cancellation；nested REQUIRES_NEW pool-exhaustion scenario (diagram is mechanism inference)；Servlet async dispatch, TLS, reverse proxy, HTTP/2, browser disconnect；standalone JVM SIGTERM or orchestration-platform draining；identity, inventory, payment, idempotency, broker/event handoff；performance/load testing；website browser rendering/accessibility (separate site QA, outside this experiment)
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### Spring 事务代理实验 {#experiment-spring-transaction-proxy}

[下载源码包](/examples/spring-transaction-proxy.zip)。历史运行范围：完整源码的 10 个事务场景：代理/自调用、共享 rollback-only、独立事务、回滚规则、绑定连接。

关联知识：[Spring 事务调用链：从代理入口到数据库连接](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：JDK 21；Spring Framework 6.2.19；H2 2.3.232；Gradle 8.10.2
- SHA256：642f64c2ed79b7a1f2387fdfba496344f071de85208f4aa9a340ac1f83c47f4c
- 未覆盖：目标 MySQL/PostgreSQL 驱动与隔离行为；HTTP、线程池与分布式事务
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### Go 服务生命周期实验：HTTP、工作池、调用与停机 {#experiment-go-service-lifecycle}

[下载源码包](/examples/go-service-lifecycle.zip)。历史运行范围：25 个顶层测试、26 个子测试，无跳过；真实 main 的 SIGTERM 排空/期限取消、启动失败和已启动池的完成信号；普通与 race 构建的真实子进程、race 测试和 vet；四个错误响应/媒体类型/截断响应/漏 join 反例被对应断言识别。

关联知识：[有界并发与 goroutine 所有权：启动以后谁等待、谁收尾](/knowledge/go/concurrency/bounded-work.html)、[下游 HTTP 调用：连接复用、超时预算与有限重试](/knowledge/go/http/client-budgets.html)、[HTTP 管线与响应合同：谁解析、谁调用、谁写回](/knowledge/go/http/request-response-contract.html)、[优雅停机评审：停止接单以后，哪些工作还欠着](/knowledge/go/lifecycle/graceful-shutdown.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：go go1.27.1 linux/amd64；mermaid 11.17.2；codehike 1.1.0；node 24.19.0；gin 1.12.0 source review only
- SHA256：de1a3140d6d70625f2abaf0133a78037714ceb7affcde6a20be29d02f7f92ed3
- 未覆盖：Gin runtime；TLS/HTTP2/HTTP3/proxies；Kubernetes/readiness propagation/rolling deploy；real database/durable queue/idempotency/crash recovery；cross-platform signal behavior；production load/performance；second force signal
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### Go context 时序实验 {#experiment-go-context-cancellation}

[下载源码包](/examples/go-context-cancellation.zip)。历史运行范围：标准库的 16 个顶层测试、4 个子测试、3 个可执行示例；取消传播、预算、返回策略、协程收尾和内存副作用。

关联知识：[Go 请求取消：从 context 传播到提交结果](/knowledge/go/concurrency/context-cancellation.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Go 1.27.1 linux/amd64
- SHA256：8de924f948adc8fd7222474fad7aadccff05154e12e824d906d1fe1a7ddea429
- 未覆盖：真实数据库集成；HTTP 网络取消；生产负载
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### 订单数据一致性实验：库存、幂等、事件、缓存与恢复 {#experiment-data-consistency}

[下载源码包](/examples/data-consistency.zip)。历史运行范围：真实单节点 MySQL 与 Redis 的23个基础场景；受控持久接收端的 outbox/去重状态机；真实 SQL、Redis、会话、镜像与清理证据经过独立复核。

关联知识：[缓存新鲜度与失效：数据库已经新了，读者为什么仍看见旧值](/knowledge/data/cache/invalidation-freshness.html)、[并发不变量与隔离：库存为什么会被两个请求同时看见](/knowledge/data/transactions/inventory-invariants.html)、[数据库与事件交接：outbox、重投与消费去重](/knowledge/distributed/events/transactional-outbox.html)、[未知结果下的幂等：第一次可能已成功，第二次怎么办](/knowledge/distributed/reliable-interactions/idempotency.html)、[一致性恢复演练：订单、库存、事件与读模型如何对账](/cases/orders/consistency-recovery.html)。

包内 NOT_RUN 是源码冻结时的历史说明；精确快照随后已执行，[2026-10-02 的验证摘要](/examples/data-consistency-verification.json)记录真实 MySQL/Redis 的范围与三条主动断线后的关闭警告。源码 ZIP 保持原身份；受控接收端并非真实 broker。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：MySQL 8.4.7 / InnoDB / REPEATABLE READ；Redis 7.4.7 / Alpine 3.21；GitHub-hosted Ubuntu 24.04
- SHA256：a7cbd725764ac9266042e8ba93954c6e6377065f2ea690cfd4963c42147e5e22
- 未覆盖：真实 Kafka/RocketMQ 的 producer/ack/offset/重平衡；多 relay 租约、外部不可回滚副作用；HTTP 断链、数据库进程掉电或磁盘故障；Redis 复制与故障切换；生产负载、容量及线上迁移；任意 Unicode/大小写身份规则
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### 身份与对象授权模型：撤销、租户、动作和提交版本 {#experiment-security-boundaries}

[下载源码包](/examples/security-boundaries-lab.zip)。历史运行范围：Python 3.12.14 标准库，固定整数时间、有限顺序状态模型；声明配置与 nbf/exp 边界；当前状态与旧缓存对撤销的可见差异；90 个固定主体/租户/对象/动作组合与独立允许集合逐项比对，拒绝读无正文，拒绝写无业务副作用；成员撤销、动作处理器绑定、归属转移、委托期限/撤销/对象/接收者/代次及提交重查；r2：在线/缓存声明和时间边界、inactive与未来观察、空委托动作、同主体陈旧准备与重复提交；逐项核对正文、备注、修订号和事件；11 个故意错误的允许变体实际运行，子进程预期退出 3 且 assertion 精确为 WRONG_ALLOW:变体名；超时、崩溃、语法/启动错误、错误 JSON、额外 stderr 或错误断言均不算通过；陈旧允许变体实际写入已转移订单，拒绝断言同时观察结果、数据和业务事件；六种实际model.py源码变异逐项运行强化后的verify.py，均因精确目标AssertionError退出1；检查空委托动作、在线声明配置、缓存inactive/未来观察、提交修订比较和递增；同主体陈旧准备及重复提交须无额外副作用；四项纯分类器反例拒绝RuntimeError、SyntaxError、ModuleNotFoundError及意外退出0。

关联知识：[身份从哪里可信：会话、令牌与撤销边界](/knowledge/security/authentication/authentication-boundaries.html)、[授权到哪一个对象：租户、主体与动作](/knowledge/security/authorization/object-tenant-authorization.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Python 3.12.14，标准库有限顺序模型
- SHA256：2af589e0b0cb6ffb7545fc69b61a1f774b6c6f2ed4462bffb88556b62f663d8b
- 未覆盖：TrustedIdentity/VerifiedClaims 仅是夹具与可信适配层前置假设，不是凭据验证或防伪类型；没有账号、密钥、密码学、Cookie/TLS、HTTP、数据库、网络或多节点缓存；提交重查与写入原子性是假设；fixture 转移/成员/委托事件不是带权限的公开管理接口；有限模型不证明完整安全性，不做性能判断；这 11 个特定坏实现不代表所有攻击方式；错误代码仅供实验；不验证真实框架入口是否遗漏授权，不验证数据库并发；仅六种已知验证缺口，不证明完整安全性；同进程顺序模型，可信身份和原子提交仍是前置假设；不新增IdP、密码学或数据库证据
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

### BeanDefinition 定位、注册与创建实验 {#experiment-spring-definition-execution}

[下载源码包](/examples/spring-bean-definition-lab.zip)。历史运行范围：Temurin JDK21.0.12.1+1，Gradle8.10.2，Spring6.2.19；最终依赖锁后全新编译：13场景/61断言通过及Main四行输出；无外部系统。

关联知识：[BeanDefinition 从哪里来：定位、解析、注册与实例化的边界](/knowledge/frameworks/spring-container/bean-definition-registration.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Temurin JDK 21.0.12.1+1；Spring Framework 6.2.19；Gradle 8.10.2
- SHA256：37eba26c6f71ad51b8e0fe12d1311f37c940b071c350ac270d28e737b8a7ea0c
- 未覆盖：未运行Boot/Web/AOT/后台初始化/循环依赖/代理/FactoryBean产物或自定义scope；首次无锁执行为历史记录，不额外算覆盖；Gradle有通用废弃API提示，未验证Gradle9
- 此处汇总已有运行记录；收录到目录不会增加实验覆盖范围

</details>

## 自己运行前

先阅读每个包的 README、版本和清理说明，使用隔离教学环境。不要把故障注入指向业务数据库；不要把凭据、真实用户资料或生产日志放进练习产物。运行失败时记录它实际失败的层次，不以“没有异常”替代业务结果。
