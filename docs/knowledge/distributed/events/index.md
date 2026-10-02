---
title: 事件架构
description: 保存已发生的事实及尚欠的交接，分清交付与消费提交。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 事件架构

[知识目录](/knowledge/) / [消息与分布式](/knowledge/distributed/)

保存已发生的事实及尚欠的交接，分清交付与消费提交。

## 阅读定位

本地事务如何共同提交业务事实；需要区分交付、处理与确认。

Outbox 保存已成立事实和待交接责任；relay 允许重投；消费者把去重和自己的副作用共同提交。不同边界承担不同原子性。

## 怎样选择阅读入口

先读为什么需要持久交接，再追踪发布后未标记窗口，最后检查消费共同提交与联合恢复。真实 broker 的 ack/offset 属于后续产品机制。

常见混淆：sent 标记不证明消费者已处理；dedup 存在也可能是错误地提前单独提交；event_id 不变时内容也应保持合同。

**小目标：**把崩溃放在交付前后和消费提交前后，列每个持久状态，并说明重投能恢复哪一种。

## 可读主题

- [数据库与事件交接：outbox、重投与消费去重](/knowledge/distributed/events/transactional-outbox.html)：把订单提交后的通知责任保存到 outbox，用可控崩溃点验证重投与消费去重，明确原子边界、顺序、积压和人工恢复。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

Outbox 的真实 broker 实现、CDC、事件 Schema、事件溯源。这些是后续主题，未完成前不会产生空链接。
