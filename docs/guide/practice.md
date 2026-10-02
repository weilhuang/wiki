---
title: 实验与评审的阅读入口
description: 从问题、预测、观察和局限组织练习。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
<div id="实验与评审" class="legacy-anchor" aria-hidden="true"></div>

# 实验与评审的阅读入口

练习要检验一个解释。先写预测，再安排输入和时序；如果结果不同，指出哪项假设被推翻。

<div id="用一个真实章节练习" class="legacy-anchor" aria-hidden="true"></div>

## 从一个具体知识点开始

例如读 [context 的时序结果表](/knowledge/go/concurrency/context-cancellation.html#_2-跑实验-不要只断言一个-error)，先预测“副作用已发生后才取消”会留下什么。再运行相应源码，分别观察错误返回与 saved，而不是只检查函数有没有报错。最后改变一个条件，说明数据与返回策略哪一个变了。

<div id="每次实验保存六件事" class="legacy-anchor" aria-hidden="true"></div>

## 记录实验过程

1. 要区分的解释与不允许破坏的业务合同
2. 固定输入、环境与版本；教学替身和真实服务分开
3. 正常路径与一项有区分力的错误实现
4. 同时观察返回、业务事实和资源收尾
5. 实际命令、结果和与预测不同的地方
6. 清理、未覆盖条件与下一项验证

这些记录帮助复现，不是用日志数量证明正确。没有执行的步骤明确写未运行，失败也不要改成一份预期输出。

<div id="各路径的运行入口" class="legacy-anchor" aria-hidden="true"></div>

## 找到对应运行入口

- [Spring 服务边界实验](/resources/experiments.html#experiment-spring-service-boundaries)：容器、MVC 与连接资源
- [Go 服务生命周期实验](/resources/experiments.html#experiment-go-service-lifecycle)：HTTP、工作池、客户端和进程
- [订单数据一致性实验](/resources/experiments.html#experiment-data-consistency)：库存、幂等、事件、缓存和恢复
- [全部实验与固定版本](/resources/experiments.html)：包括独立事务、context、HashMap、定义注册及架构顺序模型

运行前阅读该包的安全范围与清理说明，不将故障注入指向业务环境。

<div id="如何评审一个设计" class="legacy-anchor" aria-hidden="true"></div>

## 比较选择与代价

把目标与非目标、硬约束、最简单基线、两个备选方案以及失败后的动作写到同一页。用一个改变条件的例子解释何时应改选；涉及迁移时指出继续、停止与回退条件。

[场景与排障](/cases/)提供完整任务，[复习与推理](/resources/review.html)帮助选择要检验的问题。通过本页练习不等于完成所有环境或获得某个职级。
