---
title: 系统架构与演进
description: 从业务约束和变化成本出发选择结构。模式用于解释一个决定解决了什么、又引出了什么。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 系统架构与演进

从业务约束和变化成本出发选择结构。模式用于解释一个决定解决了什么、又引出了什么。

## 进入前与领域边界

能描述业务目标、失败影响和已有边界；不要求预先选择微服务或消息系统。

局部机制正确不代表整体方案适用。规模、组织、数据迁移和运维责任需要单独论证。

## 核心关系与阅读顺序

业务对象和不变量确定需要保护的事实，模块组织代码责任，数据所有权限制写入入口，事务和部署边界决定失败如何显现。选择结构以后，还要让权限、用户事件、资源与恢复责任在同一变更上成立。

从具体变化与事实边界进入，比较最简单的充分方案；需要独立演进时再读拆分与迁移案例。最后以一个取消流程串起授权、服务目标、发布峰值和停止条件，把设计变成可以被观察与反例推翻的决定。

常见误区：结构图不会自动提供一致性、隔离或容量；同名端口换成远程调用后，失败与返回语义可能改变；回退必须满足数据和交接事实的前提。

**综合任务**：给同一订单变更写两个都合理的方案，改变一项硬约束后重新选择。写清哪些事实能继续、哪些必须停止、什么条件允许旧代码接管，以及尚未执行的真实系统验证。

## 从分类进入

### 建模与边界

用责任、依赖方向和数据归属界定模块。

[分类导读](/knowledge/architecture/boundaries/)

- [模块边界如何抵抗变化：依赖、数据与测试](/knowledge/architecture/boundaries/module-boundaries.html)：用取消订单、替换存储和隔离导出三次变化，比较分层、端口适配器、模块化单体与服务拆分各自限制了什么，以及哪些代价仍须承担

后续范围：质量属性的量化取舍、限界上下文与聚合建模。

### 代码设计模式

围绕变化维度比较抽象和较简单的实现。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：策略、工厂、适配器、装饰器、状态。

### 应用架构

比较结构对测试、部署、数据和协作的影响。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：真实应用结构与架构约束检查、CQRS。

### 架构演进

先判断是否值得变化，再设计可观察、可停止的小步迁移。

[分类导读](/knowledge/architecture/evolution/)

- [订单模块要不要拆成服务：从不拆的理由到可回退的迁移](/cases/architecture/order-service-extraction.html)：用同一个订单案例比较模块化单体、查询与异步能力抽离、独立订单服务，把数据所有权、失败语义、资源成本和停止条件写成可评审的决定

后续范围：Strangler Fig、防腐层、分支抽象、数据回填。

### 业务场景

用跨机制案例检验边界选择和失败处理。

[分类导读](/knowledge/architecture/business-cases/)

- [一致性恢复演练：订单、库存、事件与读模型如何对账](/cases/orders/consistency-recovery.html)：把并发、未知结果、重投、消费中断与陈旧缓存放进同一恢复演练，用联合查询、ADR、运行手册和兼容迁移完成设计评审。
- [订单服务评审：把对象、HTTP、事务和资源合同接起来](/cases/orders/local-service-boundary.html)：以六类可重复故障审查订单创建服务，提交包含失败矩阵、资源责任、回归证据与演进限制的一页架构决策。
- [订单演进评审：权限、服务目标与事实所有权](/cases/orders/reliability-review.html)：在保留本地订单写入的起点上，评审取消与库存释放交接，写清权限矩阵、用户目标、发布峰值、失败责任以及何时只能前向修复

后续范围：真实库存预留与支付回调、批处理、跨租户委托。

### 评审与复盘

把约束、备选方案、证据和退出条件放在同一份决定中。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：代表性负载与容量验证、成本量化、组织决策复盘。

## 如何与其他领域连接

[模块与事实边界](/knowledge/architecture/boundaries/module-boundaries.html)把变化成本接回数据所有者与提交范围；[取消流程评审](/cases/orders/reliability-review.html)再联合[对象授权](/knowledge/security/authorization/object-tenant-authorization.html)、[服务事件与目标](/knowledge/cloud/observability/service-level-signals.html)、[消息确认](/knowledge/distributed/messaging/delivery-ack-boundaries.html)和[发布排空](/knowledge/cloud/lifecycle/readiness-draining.html)。已有[拆分案例](/cases/architecture/order-service-extraction.html)与[恢复案例](/cases/orders/consistency-recovery.html)提供不同约束下的完整推理，有限模型仍不能替代真实系统验证。
