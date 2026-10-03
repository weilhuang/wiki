---
title: 运行时
description: 从可观察行为进入调度、netpoll、GC 和分配实现。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 运行时

[知识目录](/knowledge/) / [Go 工程](/knowledge/go/)

从可观察行为进入调度、netpoll、GC 和分配实现。

## 阅读定位

能读 goroutine、channel 和函数调用栈；诊断主文补充 G、M、P 与采样的含义。

goroutine 可能正在执行、已经就绪但尚未运行，或等待某个条件。GOMAXPROCS 约束 Go 执行资源；channel 与网络就绪通过不同路径唤醒工作。应用任务数量还可能在执行许可之外增长。

## 怎样选择阅读入口

先用有限计算、channel、loopback TCP 和固定输入堆积区分状态，再对照栈、CPU profile、block profile 与 execution trace。观察指向某个等待条件后，回到业务所有者和下游调用预算寻找原因。

常见混淆：goroutine 多不等于 CPU 忙；IO wait 不能单独证明下游慢；累积阻塞时间不是请求墙钟延迟；一次没有发现问题也不证明生产容量、调度公平或长期无泄漏。

**小目标**：为 CPU 低而 goroutine 增多提出两个解释，选择能排除其中一个的下一份证据。记录输入、采样窗口和完成数量，再说明证据覆盖不到的环境差异。

## 可读主题

- [goroutine 为什么在等：调度、netpoll 与诊断证据](/knowledge/go/runtime/scheduler-netpoll-diagnosis.html)：沿四个有界真实进程区分计算、channel 阻塞、TCP 网络等待和工作堆积，用栈、CPU profile 与 trace 逐步缩小判断范围

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

栈增长、内存分配与GC、cgo与系统调用、代表性负载下的运行时诊断。这些是后续主题，未完成前不会产生空链接。
