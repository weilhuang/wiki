---
title: 云原生与可靠性
description: 从进程和资源出发，把交付、观测、服务目标与恢复联系起来。平台工具不能消除应用自身的生命周期责任。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 云原生与可靠性

从进程和资源出发，把交付、观测、服务目标与恢复联系起来。平台工具不能消除应用自身的生命周期责任。

## 进入前与领域边界

了解进程、网络和服务调用；诊断先记录工作负载和时间范围。

本机停机不证明 Kubernetes 摘流；一次功能用例不证明容量、SLO 或多节点恢复。

## 核心关系与阅读顺序

服务目标描述用户事件，应用负责接纳和完成工作，平台通过探针、端点与路由影响请求去向。指标采样、控制面状态和进程退出各有独立的观察边界，必须在同一时间线对齐。

先用服务事件定义分母与好事件，再比较比例、分布和资源等待；随后把发布期间的路由传播、应用排空与终止预算放进一条失败时间线。需要解释某个栈或查询时，再回到运行时和数据专题。

常见误区：零流量不能直接填成全部成功；平均实例百分位不能得到整体百分位；readiness 变化不是全链路屏障，进程内停机通过也不能证明集群摘流。

**综合任务**：为一个订单接口写出用户事件与好事件条件，安排发布期间的迟到请求，分别记录路由、接纳、完成与清理的观察。说明有限样本、顺序模型与真实部署各自还缺什么证据。

## 从分类进入

### Linux 与进程

用进程、描述符和资源限制理解运行现场。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：信号、namespace/cgroup、页缓存、资源统计。

### 容器与工作负载

区分镜像、运行用户、网络和状态卷的责任。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：镜像分层、Docker、Pod、Deployment、存储。

### 生命周期与弹性

启动、就绪、接纳和退出共同决定变更窗口。

[分类导读](/knowledge/cloud/lifecycle/)

- [就绪与排空：发布期间谁还接请求](/knowledge/cloud/lifecycle/readiness-draining.html)：沿 Kubernetes 1.34 的探针、EndpointSlice 和终止时序，区分路由传播、应用接纳、在途完成与依赖释放，并用有限模型暴露失败窗口

后续范围：真实集群摘流与故障实验、PDB、HPA、requests/limits。

### 交付与平台

同一制品逐步提升环境，数据变更需要兼容窗口。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：CI/CD、灰度、功能开关、回滚、平台治理。

### 观测与服务目标

选择能回答问题的指标、日志和追踪，控制基数与隐私。

[分类导读](/knowledge/cloud/observability/)

- [延迟与错误怎样变成服务目标：RED、USE 与 SLO](/knowledge/cloud/observability/service-level-signals.html)：从一次请求的计数边界出发，用固定样本推导服务指标、延迟分布和错误预算，并识别聚合、低流量、采样与高基数陷阱

后续范围：遥测管线与OpenTelemetry、告警窗口与误报、真实负载与预算校准。

### 性能与故障定位

用等待、资源持有与负载区分相似症状。

[分类导读](/knowledge/cloud/performance/)

- [接口慢而数据库 CPU 不高：先查连接等待](/troubleshooting/connection-waiting.html)：用同一时刻的连接池状态、持有者和等待者证据，区分借连接排队、事务内外部等待与数据库执行等待。

后续范围：排队、Little 定律、profile、连接耗尽。

### 恢复与复盘

恢复必须对账并定义停止条件，不能只看进程重新启动。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：备份演练、RPO/RTO、灾备、故障注入。

## 如何与其他领域连接

[服务事件与目标](/knowledge/cloud/observability/service-level-signals.html)先界定用户观察，再用[Go 运行时证据](/knowledge/go/runtime/scheduler-netpoll-diagnosis.html)或[连接等待](/troubleshooting/connection-waiting.html)排除局部原因。[就绪与排空](/knowledge/cloud/lifecycle/readiness-draining.html)把平台时序接回[应用停机](/knowledge/go/lifecycle/graceful-shutdown.html)；Kubernetes 来源复核和顺序模型仍需真实集群验证。恢复数据时，继续用[订单联合对账](/cases/orders/consistency-recovery.html)核对业务事实。
