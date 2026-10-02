---
title: 数据一致性：学习导读
description: 用同一个订单与库存场景，将并发不变量、未知结果、事件交接、缓存与恢复对账连成闭环。
prev: false
next: false
lastUpdated: false
---

# 数据一致性

“放进事务里”“失败就重试”“加一层缓存”都不足以说明系统正确。先要写清楚哪条业务事实必须一直成立，以及发生故障后从哪里重新判断它。本路径共用订单、库存和订单投影，避免每章换一套没有关联的小例子。

## 进入前需要什么

理解 SQL 查询/更新、唯一约束、提交/回滚，能够追踪两个请求的执行交错。若还不能区分“客户端失败”和“操作未提交”，先阅读[Spring 事务边界](/learn/spring-service-boundaries/transaction-proxy)或[Go 请求取消](/learn/go-service-lifecycle/context-cancellation)；不必同时掌握两门语言。

实验使用固定版本 MySQL 8.4.7、InnoDB 与 Redis 7.4.7。隔离级别、索引、autocommit、会话与镜像身份都属于证据，不能只写一句“数据库版本差不多”。

## 五章如何接起来

| 顺序 | 章节 | 本章必须留下的证据 |
| --- | --- | --- |
| 1 | [并发不变量与隔离](/learn/data-consistency/invariants-isolation-locks) | 两会话反例、受影响行数、等待与死锁结果 |
| 2 | [未知结果下的幂等](/learn/data-consistency/idempotency-unknown-outcomes) | 同键并发裁决、payload 冲突、提交前后中断及保存的业务结果 |
| 3 | [outbox 与消费去重](/learn/data-consistency/outbox-consumer-dedup) | 各崩溃点的持久状态、重复投递与消费副作用计数 |
| 4 | [缓存新鲜度与失效](/learn/data-consistency/cache-freshness-invalidation) | 旧值回填交错、版本拒绝、失效丢失和过期后的保证退化 |
| 5 | [一致性恢复演练](/learn/data-consistency/consistency-recovery-review) | 联合对账、恢复重放与具体 schema 迁移的结果 |

第一章建立数据库内的不变量；第二章处理调用方无法确认的结果；第三、四章越过组件边界；最后把所有持久状态放在一起对账。

## 实验入口与范围

[下载数据一致性实验源码](/examples/data-consistency.zip)。README 给出 Python、Docker Compose 入口和固定镜像台账。实验创建独立临时环境并清理自身资源，不接入已有业务数据库；运行前先阅读数据范围和资源要求。

全量入口包含二十三个场景，真实访问 MySQL 和 Redis。事件接收端使用受控持久表，目的是观察协议状态与崩溃窗口，**没有验证真实消息中间件的 producer、ack 或 offset**。单节点缓存结果也不代表复制、故障切换和生产容量已经验证。


::: info 2026-10-02 的后续验证记录
下载包保持冻结源码的原始指纹，包内 README 与 RESULT-CONTRACT 中的 NOT_RUN 是冻结时状态。该精确快照随后在 [GitHub Actions 第 36991587537 次运行](https://github.com/weilhuang/wiki/actions/runs/36991587537)完成全部二十三项真实 MySQL/Redis 场景，并经过独立证据复核；[持久验证摘要（JSON）](/examples/data-consistency-verification.json)记录源码、镜像、结果与清理。三次主动终止连接后的有界关闭警告如实保留。这次验证仍不覆盖真实 broker 或生产环境。
:::

## 走完路径的标准

提交一份不变量清单和恢复报告。面对重复下单、响应丢失、relay 重投、消费中断、缓存陈旧和恢复重放，逐项给出数据库事实、用户可见结果、未完成工作和安全恢复入口。

报告必须包含联合对账查询及实际返回值，解释一次错误实现为什么会被反例识别。最后选择同步提交与异步投影的边界，写明延迟、积压、幂等记录保留、人工介入和演进成本；不能用“最终一致”替代时间与责任合同。
