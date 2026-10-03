---
title: 生命周期与弹性
description: 启动、就绪、接纳和退出共同决定变更窗口。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 生命周期与弹性

[知识目录](/knowledge/) / [云原生与可靠性](/knowledge/cloud/)

启动、就绪、接纳和退出共同决定变更窗口。

## 阅读定位

能区分接纳新工作与等待旧工作，知道路由状态会传播。

探针、端点消费者与应用分别持有状态。删除后的控制面与kubelet链并行，停止接纳和依赖释放仍由应用所有者完成。

## 怎样选择阅读入口

先分清startup/readiness/liveness，再追踪EndpointSlice与终止时序，最后用预算和迟到请求检验发布方案。

常见混淆：ready=false不是全链路屏障，preStop不赠送额外宽限，API对象消失不保证旧进程已结束。

**小目标**：安排端点已变而路由未刷新的迟到请求，分别写出路由选择、应用拒绝、旧工作完成与依赖回收证据。

## 可读主题

- [就绪与排空：发布期间谁还接请求](/knowledge/cloud/lifecycle/readiness-draining.html)：沿 Kubernetes 1.34 的探针、EndpointSlice 和终止时序，区分路由传播、应用接纳、在途完成与依赖释放，并用有限模型暴露失败窗口

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

真实集群摘流与故障实验、PDB、HPA、requests/limits。这些是后续主题，未完成前不会产生空链接。
