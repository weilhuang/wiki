---
title: 后端工程知识站
titleTemplate: false
description: 从机制解释、反例验证到系统评审，沿三条闭合路径学习后端服务边界与数据一致性。
prev: false
next: false
lastUpdated: false
---

# 后端工程知识站

这里按问题的先修关系组织知识：先弄清楚状态和资源由谁负责，再用反例检验理解，最后把多个边界放回同一个服务里评审。阅读顺序由知识依赖决定。

## 选择一条学习路径

首批内容围绕三个能独立走完的主题，共十五章。每条路径都从基本合同进入机制、诊断和综合演练。

| 路径 | 从什么问题开始 | 最后交付什么 |
| --- | --- | --- |
| [Spring 服务边界](/learn/spring-service-boundaries/) | 对象何时可用，请求失败后数据和资源处于什么状态 | 对象所有权图、HTTP/数据失败矩阵、连接预算和服务边界 ADR |
| [Go 服务生命周期](/learn/go-service-lifecycle/) | 请求结束以后，谁还在工作、谁负责收尾 | 入口合同、有界并发与调用预算、停机证据和运行手册 |
| [数据一致性](/learn/data-consistency/) | 并发和超时发生时，订单、库存和读模型如何保持约定 | 不变量、幂等与事件合同、缓存风险表和恢复对账报告 |

熟悉 Java 的读者可先走 Spring 路径；熟悉 Go 的读者可先走 Go 路径。两条路径都会遇到“请求失败，但业务可能已经完成”，接着进入数据一致性。无需先学会另一门语言。

## 带着具体问题查找

- **注解明明写了，事务为何没有按预期回滚？** 看[事务代理入口与共享回滚](/learn/spring-service-boundaries/transaction-proxy#call-paths)
- **超时已经返回，写入是否还能继续？** 看[取消信号与业务结果](/learn/go-service-lifecycle/context-cancellation)
- **线程越加越多，服务为何仍在等连接？** 看[连接持有期和超时预算](/learn/spring-service-boundaries/connection-budget-timeouts)
- **一个分支报错后，其他 goroutine 由谁回收？** 看[有界并发与所有权](/learn/go-service-lifecycle/bounded-concurrency-ownership)
- **第一次请求结果未知，第二次怎样重试？** 看[幂等键、保存结果与有效期](/learn/data-consistency/idempotency-unknown-outcomes)
- **数据库、消息和缓存恢复以后，凭什么确认一致？** 看[联合对账与恢复演练](/learn/data-consistency/consistency-recovery-review)

## 如何判断自己学会了

读代码前先预测结果，运行后同时观察响应、最终数据和资源状态。再改变一个条件，构造能推翻错误解释的反例。路径终章要求写出取舍和未覆盖范围，不能只提交一张“测试通过”的截图。

[实验与评审](/guide/practice)给出具体做法；[知识地图](/guide/knowledge-map)说明三个主题之间的依赖，以及当前没有覆盖的领域。
