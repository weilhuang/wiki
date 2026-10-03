---
title: 消息与分布式
description: 多个参与者无法共享同一次观察时，要分别说明身份、确认、顺序、重试和恢复。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 消息与分布式

多个参与者无法共享同一次观察时，要分别说明身份、确认、顺序、重试和恢复。

## 进入前与领域边界

本地事务与请求响应；每篇另列需要理解的失败模型。

一个受控协议替身能解释交错，不能代替真实 broker 的确认、复制、重平衡或网络分区验证。

## 核心关系与阅读顺序

本地提交、发送、接收、处理和确认发生在不同参与者。调用方未知不等于业务回滚；消息重复也不必然产生重复副作用。协议必须把身份、责任、中间状态和恢复条件说清。

先理解单次业务的局部原子性，再处理未知结果和重试，随后研究事件交接、消费与恢复；共识和 broker 实现另按故障模型深入。

常见误区：一行 outbox 不自动保证最终交付；一张 dedup 表不证明它与副作用共同提交；受控替身的时序不能升级为某个消息产品的保证。

**综合任务**：把确认丢失分别放在发送侧和消费侧，列出每个持久状态及下一次安全动作，再说明保留期结束后哪些保证失效。

## 从分类进入

### 可靠交互

未知结果需要稳定身份和查询入口，重试需要预算与责任。

[分类导读](/knowledge/distributed/reliable-interactions/)

- [未知结果下的幂等：第一次可能已成功，第二次怎么办](/knowledge/distributed/reliable-interactions/idempotency.html)：为订单创建定义稳定操作身份、同键冲突、事务内裁决与结果查询，验证提交前后断点及幂等记录过期后的保证退化。

后续范围：退避、抖动、熔断、隔离舱、限流。

### 事件架构

保存已发生的事实及尚欠的交接，分清交付与消费提交。

[分类导读](/knowledge/distributed/events/)

- [数据库与事件交接：outbox、重投与消费去重](/knowledge/distributed/events/transactional-outbox.html)：把订单提交后的通知责任保存到 outbox，用可控崩溃点验证重投与消费去重，明确原子边界、顺序、积压和人工恢复。

后续范围：Outbox 的真实 broker 实现、CDC、事件 Schema、事件溯源。

### 消息投递与产品机制

先定义确认含义，再比较队列、日志与消费模型。

[分类导读](/knowledge/distributed/messaging/)

- [确认了什么：投递、重投、顺序与消费提交](/knowledge/distributed/messaging/delivery-ack-boundaries.html)：沿一条订单事件区分生产确认、broker 保存、消费者收到与业务提交，再推导丢确认、毒消息和按键顺序的恢复选择

后续范围：真实 broker 实验、分区重平衡、跨副本故障恢复、RocketMQ。

### 消息恢复与运维

积压、去重、保留期与投影需要共同恢复。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：毒消息隔离、有限重放、迁移消费者。

### 协调与共识

把故障模型、时钟假设和所有权有效期写清。

[分类导读](/knowledge/distributed/coordination/)

- [租约过期以后：旧持有者为什么仍需 fencing](/knowledge/distributed/coordination/lease-fencing.html)：用暂停后恢复的两个工作者解释租约与资源端栅栏，追踪单调 token、同租约多操作、重放去重和水位恢复的边界

后续范围：Raft、quorum、选主、真实协调服务与故障恢复。

### 跨边界数据协作

不同方案改变原子边界，也增加新的中间状态。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：Saga、补偿、TCC、2PC/XA、跨服务查询。

### 任务与状态

任务需要认领、接管、结果和终止协议。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：持久工作流、定时调度、断点恢复。

## 如何与其他领域连接

[幂等](/knowledge/distributed/reliable-interactions/idempotency.html)把重复尝试接回本地裁决，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存待交接责任。[确认边界](/knowledge/distributed/messaging/delivery-ack-boundaries.html)继续区分保存、投递与消费提交；[租约与fencing](/knowledge/distributed/coordination/lease-fencing.html)解释接管之后旧工作如何被资源拒绝。目标对象还需经过[主体与租户授权](/knowledge/security/authorization/object-tenant-authorization.html)。
