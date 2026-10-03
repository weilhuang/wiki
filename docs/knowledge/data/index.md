---
title: 数据与存储
description: 先识别业务事实及不变量，再研究索引、事务、复制和派生数据如何保存或读取它。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 数据与存储

先识别业务事实及不变量，再研究索引、事务、复制和派生数据如何保存或读取它。

## 进入前与领域边界

基本 SQL、唯一约束、提交与回滚；并发例子需要区分两个会话的执行顺序。

缓存与搜索是派生视图；单数据库事务不会自动覆盖独立消息接收、外部支付或另一份投影。

## 核心关系与阅读顺序

业务不变量说明哪些状态可以成立；约束与事务决定一次写入能裁决什么；索引与锁决定访问和并发边界；缓存、搜索与投影则保存可落后的派生观察。恢复必须从权威事实向派生状态推进。

先写一个可检查的不变量，再比较 SQL 和事务方案；需要理解异常时进入访问路径、快照与锁；只有读取合同明确后才选择缓存和复制。

常见误区：每条 SQL 成功不等于业务守恒；库存非负不等于没有超卖；缓存 TTL 计量驻留时间，不直接等于源数据年龄。

**综合任务**：用两个会话争抢最后一件库存，检查库存、订单数量与业务身份，再改变缓存回填顺序，说明哪些观察足以裁决成功。

## 从分类进入

### 关系建模

业务身份和约束决定数据库能够裁决什么。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：主键与业务键、范式、Schema 演进。

### 索引与查询

从访问路径解释筛选、排序、回表和分页代价。

[分类导读](/knowledge/data/indexes/)

- [组合索引与访问路径：执行计划说明了什么](/knowledge/data/indexes/composite-index-access-paths.html)：用同一组订单数据分开解释索引定位、范围过滤、覆盖、回表、排序与优化器选择，并核对无 hint 和人为约束计划的证据边界

后续范围：B+Tree 页结构、统计信息刷新与倾斜数据、分页与索引维护。

### 事务与并发业务

以不变量和会话交错判断事务、快照和锁的边界。

[分类导读](/knowledge/data/transactions/)

- [并发不变量与隔离：库存为什么会被两个请求同时看见](/knowledge/data/transactions/inventory-invariants.html)：从库存守恒的最短反例出发，用 MySQL 两会话区分快照读、条件更新、锁定读与死锁，并留下能检查的数据库证据。
- [MVCC 的读取边界：快照、当前读与写入](/knowledge/data/transactions/mvcc-read-views.html)：用两个写读会话和一个观察会话解释 RR 与 RC 的 Read View、首次读时机、锁定读取、自己的写入以及提交回滚后的实际可见性

后续范围：undo 回收与 redo、间隙锁与死锁、更多隔离和DDL边界。

### 复制与恢复

明确读到什么、丢失多少和恢复到哪一刻。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：复制延迟、GTID、备份、RPO/RTO、在线变更。

### 缓存模型与一致性

区分命中收益、源数据年龄、失效窗口和回源成本。

[分类导读](/knowledge/data/cache/)

- [缓存新鲜度与失效：数据库已经新了，读者为什么仍看见旧值](/knowledge/data/cache/invalidation-freshness.html)：用真实 MySQL 与 Redis 的受控交错分析旧值回填、失效丢失、TTL 与版本水位，给订单查询定义可接受的陈旧边界。

后续范围：Cache Aside、穿透与击穿、多级缓存、重建。

### Redis 机制与可用性

命令原子性、持久化与复制分别影响不同故障。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：数据类型、Lua、过期淘汰、AOF、Sentinel、Cluster。

### 搜索与读模型

派生视图需要定义刷新、推进和重新生成的责任。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：倒排索引、Elasticsearch、CQRS、回放重建。

### 数据工程与流批

把指标口径、质量和同步责任连接到数据产出。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：CDC、流批取舍、事件时间、水位、回填、血缘。

## 如何与其他领域连接

[索引访问路径](/knowledge/data/indexes/composite-index-access-paths.html)解释怎样找到候选，[MVCC 读取边界](/knowledge/data/transactions/mvcc-read-views.html)解释能看到哪个版本。本地事实提交后，[Outbox](/knowledge/distributed/events/transactional-outbox.html)保存跨组件交接责任；[缓存新鲜度](/knowledge/data/cache/invalidation-freshness.html)解释读取为何仍会落后。最终用[联合恢复](/cases/orders/consistency-recovery.html)核对权威事实与派生结果。
