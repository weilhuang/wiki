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
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### HashMap JDK 21：API、实现观察与验证器回归 {#experiment-hashmap-jdk21}

[下载源码包](/examples/hashmap-jdk21-lab.zip)。历史运行范围：Temurin 21.0.12.1+1-LTS，7个公共API场景及完整调用示例；违约键的输出只属固定实现反例；同一验证命令中的4个显式可选实现观察：put第9节点、默认map第11节点、computeIfAbsent第8节点、树拆分6/7节点；逐键检查映射；5个可见错误假设分别由主异常首行指定 AssertionError 拒绝，验证器检查异常类型、对应命题消息和退出码1；整体exit0；R2验证器隔离回归：7个变异逐项要求退出1和具体目标故障证据；覆盖R1原三变异及命题/意外成功/compute映射丢失与污染。

关联知识：[HashMap 的查找、冲突与扩容](/knowledge/java/collections/hashmap.html)、[沿 OpenJDK 21 源码追踪 HashMap 的状态变化](/knowledge/java/collections/hashmap-source.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Temurin 21.0.12.1+1-LTS；OpenJDK jdk-21+35 source
- SHA256：02b804cadb81930fad375fd4cce3b08eddebdc60aebda1a7c620e2e6243d741d
- 未覆盖：不读取私有容量；位运算索引为独立模型，不能独自证明真实桶布局；不证明并发安全或性能；未执行GA二进制；仅通过Map.Entry实际类名观察Node/TreeNode；容量由固定源码推演，没有访问table字段；未测树高度/颜色/删除枚举；类型名不属于API保证；是反向命题检查，不是对JDK进行变异测试；最后一项验证独立位运算模型；变异仅作用于教学实验，不改JDK；不代表穷尽全部验证器漏洞
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### Spring 服务边界实验：容器、MVC 与连接 {#experiment-spring-service-boundaries}

[下载源码包](/examples/spring-service-boundaries.zip)。历史运行范围：4 组容器生命周期实验；5 组连接资源实验；8 个真实回环 HTTP 请求，同时核对业务副作用。

关联知识：[连接池与事务预算：请求卡住时，资源被谁占住](/knowledge/frameworks/data-access/connection-budget.html)、[容器创建与对象所有权：Bean 何时可用，谁负责关闭](/knowledge/frameworks/spring-container/bean-lifecycle.html)、[请求完成链：MVC 在哪里选择处理器、转换异常和提交响应](/knowledge/frameworks/spring-mvc/request-pipeline.html)、[订单服务评审：把对象、HTTP、事务和资源合同接起来](/cases/orders/local-service-boundary.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：jdk Temurin 21.0.12.1+1；gradle 8.10.2；springBoot 3.5.16；springFramework 6.2.19；tomcat 10.1.55；servlet 6.0；hikariCP 6.3.3；h2 2.3.232；hibernateValidator 8.0.3.Final；codeHike 1.1.0；mermaid 11.17.2
- SHA256：2b46b578290ea5f47544adcb08c53809c9cdecc6221684b45ef68a048eb30163
- 未覆盖：MySQL/PostgreSQL isolation/locks/driver cancellation；real downstream HTTP timing/cancellation；nested REQUIRES_NEW pool-exhaustion scenario (diagram is mechanism inference)；Servlet async dispatch, TLS, reverse proxy, HTTP/2, browser disconnect；standalone JVM SIGTERM or orchestration-platform draining；identity, inventory, payment, idempotency, broker/event handoff；performance/load testing；website browser rendering/accessibility (separate site QA, outside this experiment)
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### Spring 事务代理实验 {#experiment-spring-transaction-proxy}

[下载源码包](/examples/spring-transaction-proxy.zip)。历史运行范围：完整源码的 10 个事务场景：代理/自调用、共享 rollback-only、独立事务、回滚规则、绑定连接。

关联知识：[Spring 事务调用链：从代理入口到数据库连接](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：JDK 21；Spring Framework 6.2.19；H2 2.3.232；Gradle 8.10.2
- SHA256：642f64c2ed79b7a1f2387fdfba496344f071de85208f4aa9a340ac1f83c47f4c
- 未覆盖：目标 MySQL/PostgreSQL 驱动与隔离行为；HTTP、线程池与分布式事务
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### Go 服务生命周期实验：HTTP、工作池、调用与停机 {#experiment-go-service-lifecycle}

[下载源码包](/examples/go-service-lifecycle.zip)。历史运行范围：25 个顶层测试、26 个子测试，无跳过；真实 main 的 SIGTERM 排空/期限取消、启动失败和已启动池的完成信号；普通与 race 构建的真实子进程、race 测试和 vet；四个错误响应/媒体类型/截断响应/漏 join 反例被对应断言识别。

关联知识：[有界并发与 goroutine 所有权：启动以后谁等待、谁收尾](/knowledge/go/concurrency/bounded-work.html)、[下游 HTTP 调用：连接复用、超时预算与有限重试](/knowledge/go/http/client-budgets.html)、[HTTP 管线与响应合同：谁解析、谁调用、谁写回](/knowledge/go/http/request-response-contract.html)、[优雅停机评审：停止接单以后，哪些工作还欠着](/knowledge/go/lifecycle/graceful-shutdown.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：go go1.27.1 linux/amd64；mermaid 11.17.2；codehike 1.1.0；node 24.19.0；gin 1.12.0 source review only
- SHA256：de1a3140d6d70625f2abaf0133a78037714ceb7affcde6a20be29d02f7f92ed3
- 未覆盖：Gin runtime；TLS/HTTP2/HTTP3/proxies；Kubernetes/readiness propagation/rolling deploy；real database/durable queue/idempotency/crash recovery；cross-platform signal behavior；production load/performance；second force signal
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### Go context 时序实验 {#experiment-go-context-cancellation}

[下载源码包](/examples/go-context-cancellation.zip)。历史运行范围：标准库的 16 个顶层测试、4 个子测试、3 个可执行示例；取消传播、预算、返回策略、协程收尾和内存副作用。

关联知识：[Go 请求取消：从 context 传播到提交结果](/knowledge/go/concurrency/context-cancellation.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Go 1.27.1 linux/amd64
- SHA256：8de924f948adc8fd7222474fad7aadccff05154e12e824d906d1fe1a7ddea429
- 未覆盖：真实数据库集成；HTTP 网络取消；生产负载
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

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
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

### BeanDefinition 定位、注册与创建实验 {#experiment-spring-definition-execution}

[下载源码包](/examples/spring-bean-definition-lab.zip)。历史运行范围：Temurin JDK21.0.12.1+1，Gradle8.10.2，Spring6.2.19；最终依赖锁后全新编译：13场景/61断言通过及Main四行输出；无外部系统。

关联知识：[BeanDefinition 从哪里来：定位、解析、注册与实例化的边界](/knowledge/frameworks/spring-container/bean-definition-registration.html)。

<details class="verification-appendix">
<summary>版本、下载身份与未覆盖范围</summary>

- 版本：Temurin JDK 21.0.12.1+1；Spring Framework 6.2.19；Gradle 8.10.2
- SHA256：37eba26c6f71ad51b8e0fe12d1311f37c940b071c350ac270d28e737b8a7ea0c
- 未覆盖：未运行Boot/Web/AOT/后台初始化/循环依赖/代理/FactoryBean产物或自定义scope；首次无锁执行为历史记录，不额外算覆盖；Gradle有通用废弃API提示，未验证Gradle9
- 此处引用历史运行；本次目录迁移没有新增或重复计数这些用例

</details>

## 自己运行前

先阅读每个包的 README、版本和清理说明，使用隔离教学环境。不要把故障注入指向业务数据库；不要把凭据、真实用户资料或生产日志放进练习产物。运行失败时记录它实际失败的层次，不以“没有异常”替代业务结果。
