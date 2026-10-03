---
title: 执行与编排
description: 任务的接纳、排队、运行和取消有不同资源成本。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 执行与编排

[知识目录](/knowledge/) / [Java 平台](/knowledge/java/)

任务的接纳、排队、运行和取消有不同资源成本。

## 阅读定位

能区分同步调用、任务执行和取回结果；先理解提交与 Future.get 的可见性边界。

执行器管理任务的接纳与执行，队列保存尚未开始的工作，工作线程承担运行，Future 保存可查询的完成状态。拒绝和关闭改变谁还对任务负责，并不自动兑现所有等待者的结果。

## 怎样选择阅读入口

先沿 execute 的核心线程、入队、扩展与拒绝分支安排四个任务，再看提交异常归属和关闭竞态。最后把线程数、队列及下游连接放进同一资源预算。

常见混淆：最大线程数不会跳过成功入队的分支；submit 返回 Future 不代表调用方会自动看到异常；shutdownNow 返回待执行包装对象不保证其 Future 已取消。

**小目标**：在队列已满、刚入队便关闭和任务抛异常三种场景中，逐项标出接纳结果、执行次数、异常观察者和最终收尾责任。

## 可读主题

- [线程池如何接纳任务：线程、队列与拒绝](/knowledge/java/juc-execution/executor-admission.html)：沿 JDK21 execute、FutureTask 与 shutdown 的真实分支解释任务接纳、异常归属和关闭后的责任

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

更多拒绝策略与 ThreadFactory 失败、CompletableFuture、ForkJoin、虚拟线程。这些是后续主题，未完成前不会产生空链接。
