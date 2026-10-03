---
title: 数据与消息一致性
description: 从业务不变量走到未知结果、事件交接、缓存和联合恢复，解释每个局部承诺。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 数据与消息一致性

从业务不变量走到未知结果、事件交接、缓存和联合恢复，解释每个局部承诺。

## 阅读准备与可跳过条件 {#entry}

SQL 与唯一约束；事务提交和回滚；两个会话的交错执行。这些是进入本路线的基础，不是要求先完成整站。

已经熟悉一个阶段时，先尝试该阶段任务；若能说明成立条件、反例和未验证范围，可以跳过阅读。需要定位具体问题时，直接进入知识页。

## 1. 先定义一次业务的事实 {#stage-1}

先解释一次写入怎样保持业务守恒，再让重试复用同一份裁决。

- [并发不变量与隔离：库存为什么会被两个请求同时看见](/knowledge/data/transactions/inventory-invariants.html)（主线）：用业务结果比较条件更新与锁定读取
- [MVCC 的读取边界：快照、当前读与写入](/knowledge/data/transactions/mvcc-read-views.html)（选读）：需要解释读取差异时，区分普通视图、当前读取和自己的写入
- [组合索引与访问路径：执行计划说明了什么](/knowledge/data/indexes/composite-index-access-paths.html)（选读）：把索引定位、过滤、取列和排序分开，并比较估计与实际计划
- [未知结果下的幂等：第一次可能已成功，第二次怎么办](/knowledge/distributed/reliable-interactions/idempotency.html)（主线）：让重复参与同一裁决而非再次执行业务

**阶段任务**：写出守恒、唯一和终态合同，给超时后的查询保留稳定身份。

## 2. 再推进跨组件责任 {#stage-2}

本地提交不能把事实自动送到消费者或缓存，必须增加持久交接与新鲜度合同。

- [数据库与事件交接：outbox、重投与消费去重](/knowledge/distributed/events/transactional-outbox.html)（主线）：区分事实提交、交付和消费提交
- [确认了什么：投递、重投、顺序与消费提交](/knowledge/distributed/messaging/delivery-ack-boundaries.html)（主线）：追踪确认究竟覆盖保存、投递还是消费提交，处理重投与按键缺口
- [租约过期以后：旧持有者为什么仍需 fencing](/knowledge/distributed/coordination/lease-fencing.html)（选读）：存在租约接管时，让接收端拒绝已被新代次取代的旧持有者
- [缓存新鲜度与失效：数据库已经新了，读者为什么仍看见旧值](/knowledge/data/cache/invalidation-freshness.html)（主线）：为不同读取定义新鲜度与恢复责任

**阶段任务**：画出交接重投与旧值回填的窗口，比较方案增加的状态。

## 3. 最后联合恢复和停止 {#stage-3}

每个组件各自恢复仍可能留下缺口，需要在同一数据集上联合对账并决定何时停止。

- [一致性恢复演练：订单、库存、事件与读模型如何对账](/cases/orders/consistency-recovery.html)（主线）：用权威事实对账、限定重放并验证兼容迁移

**阶段任务**：恢复后检查守恒、投影和待交接责任，而非只检查服务存活。

## 完成以后 {#completion}

用一个改变条件的反例检查自己的解释，再比较两个都合理的方案。路线的完成不等于职位或能力认证；留下可复核的推理比记录读过多少页更有用。

[实验与验证](/resources/experiments.html)提供完整源码、运行范围和历史记录；[复习与推理](/resources/review.html)按领域、类型与任务筛选问题。
