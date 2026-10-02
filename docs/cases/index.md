---
title: 场景与排障
description: 从可见问题选择证据，连接机制、方案与恢复责任。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 场景与排障

场景先定义业务目标和约束；排障先区分看起来相似的原因。它们都回链同一份机制知识，避免再维护一套简化答案。

## 场景方案

- [优雅停机评审：停止接单以后，哪些工作还欠着](/knowledge/go/lifecycle/graceful-shutdown.html)：把请求、后台任务、客户端连接与进程退出连接成可验证的生命周期，用真实信号子进程检验排空和强制结束。
- [一致性恢复演练：订单、库存、事件与读模型如何对账](/cases/orders/consistency-recovery.html)：把并发、未知结果、重投、消费中断与陈旧缓存放进同一恢复演练，用联合查询、ADR、运行手册和兼容迁移完成设计评审。
- [订单服务评审：把对象、HTTP、事务和资源合同接起来](/cases/orders/local-service-boundary.html)：以六类可重复故障审查订单创建服务，提交包含失败矩阵、资源责任、回归证据与演进限制的一页架构决策。
- [订单模块要不要拆成服务：从不拆的理由到可回退的迁移](/cases/architecture/order-service-extraction.html)：用同一个订单案例比较模块化单体、查询与异步能力抽离、独立订单服务，把数据所有权、失败语义、资源成本和停止条件写成可评审的决定

## 排障入口

- [接口慢而数据库 CPU 不高：先查连接等待](/troubleshooting/connection-waiting.html)：区分未借到连接、持有连接做外部等待与 SQL 自身等待
- [catch 住异常仍回滚](/knowledge/frameworks/spring-transactions/proxy-call-chain.html#shared-rollback)：检查异常经过的代理边界与共享回滚标记
- [goroutine 收到取消仍未退出](/knowledge/go/concurrency/context-cancellation.html#worker-lifetime)：查停止条件、资源阻塞与等待责任
- [缓存删过仍返回旧值](/knowledge/data/cache/invalidation-freshness.html#_2-后删也有窗口-旧读者还没回来)：追踪旧读者回填的时序
- [已有去重记录却缺少投影](/knowledge/distributed/events/transactional-outbox.html#_3-消费去重的提交边界-比表名重要)：核对去重与副作用是否共同提交

这些入口定位到真正的推理段落。需要全程练习时，再进入[学习路线](/paths/)。
