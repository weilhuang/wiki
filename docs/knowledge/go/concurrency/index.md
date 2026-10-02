---
title: 并发协作与设计
description: 把取消信号、工作退出和结果回收分开，再限制并发与队列。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 并发协作与设计

[知识目录](/knowledge/) / [Go 工程](/knowledge/go/)

把取消信号、工作退出和结果回收分开，再限制并发与队列。

## 阅读定位

goroutine、channel、函数返回与 defer；不要求预先理解调度器源码。

context 发信号，工作代码选择如何退出，所有者等待并回收结果。并发数量和排队数量又是两项不同预算。

## 怎样选择阅读入口

先理解 cancel 与完成的区别，再读有界任务所有权；需要进程级等待时进入优雅停机。

常见混淆：给函数再包一层 goroutine 不会自动让被调用工作停止；最多并发 N 项不能单独限制等待队列或内存。

**小目标**：让一个工作忽略取消，预测函数、队列和进程的状态；选择明确的继续拥有或终止策略。

## 可读主题

- [有界并发与 goroutine 所有权：启动以后谁等待、谁收尾](/knowledge/go/concurrency/bounded-work.html)：用有限 fan-out 和有界任务池验证并发上限、队列拒绝、首错取消、结果回收与 goroutine 收敛。
- [Go 请求取消：从 context 传播到提交结果](/knowledge/go/concurrency/context-cancellation.html)：沿请求、工作 goroutine 和数据提交三条线理解 context，配合可运行实验区分取消信号、函数返回与业务结果。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

sync、errgroup、背压、并发测试。这些是后续主题，未完成前不会产生空链接。
