---
title: 知识地图
description: 目录、路线、场景和验证共享知识对象。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
<div id="后端工程知识地图" class="legacy-anchor" aria-hidden="true"></div>

# 知识地图

知识目录把问题放回稳定领域，路线安排有目的的阅读，场景连接多个机制。它们共享主文；下面的箭头表示建议的理解顺序，真实强先修仍以每篇的原因说明为准。

<div id="首批路径的先修关系" class="legacy-anchor" aria-hidden="true"></div>

## 从局部关系开始

- Java 对象相等性（独立专题规划） → [HashMap](/knowledge/java/collections/hashmap.html) → 并发容器与缓存选型（规划）
- [安全发布](/knowledge/java/juc-foundations/jmm-safe-publication.html) → [任务接纳与结果](/knowledge/java/juc-execution/executor-admission.html) → [线程与 GC 诊断](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)；集合与并发两条线在[Java 核心机制路线](/paths/java-core.html)中汇合
- [容器对象](/knowledge/frameworks/spring-container/bean-lifecycle.html) → [请求完成](/knowledge/frameworks/spring-mvc/request-pipeline.html) → [事务](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)与[连接](/knowledge/frameworks/data-access/connection-budget.html) → [本地服务边界](/cases/orders/local-service-boundary.html)
- [取消信号](/knowledge/go/concurrency/context-cancellation.html) → [工作退出与等待](/knowledge/go/concurrency/bounded-work.html) → [下游预算](/knowledge/go/http/client-budgets.html) → [进程排空](/knowledge/go/lifecycle/graceful-shutdown.html)
- [库存不变量](/knowledge/data/transactions/inventory-invariants.html) → [幂等](/knowledge/distributed/reliable-interactions/idempotency.html) → [Outbox](/knowledge/distributed/events/transactional-outbox.html) → [缓存](/knowledge/data/cache/invalidation-freshness.html) → [联合恢复](/cases/orders/consistency-recovery.html)
- [等待条件](/knowledge/foundations/operating-systems/blocking-waiting.html) → [结果与时序断言](/knowledge/foundations/testing/assertion-counterexamples.html) → [对象授权的反例](/knowledge/security/authorization/object-tenant-authorization.html#negative-tests)
- [可信身份与撤销](/knowledge/security/authentication/authentication-boundaries.html) → [租户、对象与动作](/knowledge/security/authorization/object-tenant-authorization.html) → [身份与多租户路线](/paths/identity-tenancy.html)

<div id="九个主题怎样分工" class="legacy-anchor" aria-hidden="true"></div>

## 按领域定位

- [Java 平台](/knowledge/java/)：从对象身份、集合与并发，连接到字节码、内存和运行时行为。语言/API 约定与某版 JDK 的实现分开阅读。
- [Go 工程](/knowledge/go/)：围绕函数合同、并发所有权、标准库服务和进程生命周期组织 Go 知识。先解释谁启动、谁等待、谁关闭，再讨论工具选择。
- [框架与服务通信](/knowledge/frameworks/)：沿请求进入、对象创建、代理调用和资源使用，解释应用框架与通信协议如何影响业务行为。
- [数据与存储](/knowledge/data/)：先识别业务事实及不变量，再研究索引、事务、复制和派生数据如何保存或读取它。
- [消息与分布式](/knowledge/distributed/)：多个参与者无法共享同一次观察时，要分别说明身份、确认、顺序、重试和恢复。
- [系统架构与演进](/knowledge/architecture/)：从业务约束和变化成本出发选择结构。模式用于解释一个决定解决了什么、又引出了什么。
- [云原生与可靠性](/knowledge/cloud/)：从进程和资源出发，把交付、观测、服务目标与恢复联系起来。平台工具不能消除应用自身的生命周期责任。
- [身份与安全](/knowledge/security/)：每次访问都要明确主体、资源、动作和信任边界，再选择认证、授权及凭据生命周期。
- [计算机基础与工程方法](/knowledge/foundations/)：数据结构、操作系统和测试方法为上层机制提供可推理的模型；构建与协作让结论能被复核。

<div id="从理解到评审" class="legacy-anchor" aria-hidden="true"></div>

## 跨过一个边界以后，为什么还要继续

事务说明本地数据是否共同提交，却不保证响应必然送达，所以还需要幂等与结果查询。Outbox 保存待交接责任，却不能消除消费重投，所以要检查消费侧共同提交。取消通知工作不再等待，却不自动回收工作，所以要明确所有者和 join。

[九域目录](/knowledge/)说明归属与内容状态；[学习路线](/paths/)说明阅读准备和阶段任务；[场景与排障](/cases/)从现象追踪责任。
