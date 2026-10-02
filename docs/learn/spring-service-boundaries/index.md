---
title: Spring 服务边界：学习导读
description: 从容器对象、MVC 响应、事务提交和连接占用四种边界，走到订单服务的综合设计评审。
prev: false
next: false
lastUpdated: false
---

# Spring 服务边界

一次请求失败后，不能只问“哪个注解没生效”。对象可能尚未初始化，输入可能根本没有进入业务，事务可能已经提交，连接也可能仍被外层调用占用。本路径把这些判断拆开，再放回同一个订单服务中。

## 进入前需要什么

能够阅读 Java 接口、构造器、异常和 `try/finally`；理解 HTTP 状态/响应体，以及 SQL 的提交、回滚和唯一约束。不要求先背 Spring 源码，也不要求部署集群。

实验使用完整 JDK 21、Gradle 8.10.2 和 Spring Framework 6.2.19。MVC 示例还固定 Boot、Tomcat 等版本，下载包记录完整依赖；已有事务实验保持独立，避免用一次依赖升级改变结论。

## 五章如何接起来

| 顺序 | 章节 | 本章必须留下的证据 |
| --- | --- | --- |
| 1 | [容器创建与对象所有权](/learn/spring-service-boundaries/bean-ownership-lifecycle) | 创建、注入、初始化、失败清理和销毁的事件顺序 |
| 2 | [MVC 请求完成链](/learn/spring-service-boundaries/mvc-request-completion) | 真实 HTTP 状态与响应体，以及业务是否进入、副作用是否发生 |
| 3 | [事务代理与连接](/learn/spring-service-boundaries/transaction-proxy) | 代理入口、最终数据库行和共享/独立事务的提交边界 |
| 4 | [连接池与事务预算](/learn/spring-service-boundaries/connection-budget-timeouts) | 连接持有期、等待数量和缩短事务范围后的对照 |
| 5 | [订单服务边界评审](/learn/spring-service-boundaries/service-boundary-review) | 同时覆盖 HTTP、数据和资源的失败矩阵与 ADR |

第一、二章先确认“谁负责”；第三、四章解释“责任在哪个边界生效”；最后一章要求据此选择设计。若只想诊断事务问题，可以直接看第三章，但综合评审仍需要前面各层的合同。

## 实验入口与范围

- [服务边界实验源码](/examples/spring-service-boundaries.zip)：对象生命周期、MVC 回环 HTTP 和连接池等待；从包内 README 的 `lifecycle`、`http`、`pool` 入口逐项运行
- [事务代理实验源码](/examples/spring-transaction-proxy.zip)：十个独立场景，断言数据库最终状态与绑定连接

H2 在这里用于验证 Spring 边界和连接持有行为。它不能代替 MySQL 的锁、隔离和驱动取消实验；这些问题在[数据一致性路径](/learn/data-consistency/)里使用目标数据库单独验证。关闭应用上下文的结果也不等于操作系统信号或 Kubernetes 排空已经通过。

## 走完路径的标准

给订单创建画一张同时标出对象所有者、数据库提交点和响应提交点的时序图。为正常请求、输入失败、业务异常、连接耗尽、提交后响应失败和关闭中请求，分别写明外部响应、最终数据、资源释放与重试判断。

最后比较长事务 Controller 与短事务应用服务两种设计。选择其中一种，说明另一种在什么条件下更合理，并提交可重复的反例、修复验证和剩余风险。[实验与评审](/guide/practice)提供证据组织方法。
