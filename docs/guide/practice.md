---
title: 实验与评审
description: 把运行前预测、反例、最终状态和范围说明组成可复查证据，而不是只收集 PASS 输出。
prev: false
next: false
lastUpdated: false
---

# 实验与评审

实验的价值在于区分两种解释。若正确实现和错误实现都能通过同一组测试，绿色结果没有证明预期合同。开始运行前，先写下你要观察的差异。

## 用一个真实章节练习

下载[Spring 事务实验](/examples/spring-transaction-proxy.zip)，对照[代理调用链](/learn/spring-service-boundaries/transaction-proxy#call-paths)。其中两条路径都执行写入并抛出运行时异常：一条从容器提供的事务代理进入，另一条在对象内部自调用。

先预测两个观察结果：调用方收到什么异常，数据库最后留下哪些行。再按包内 JDK 21、Gradle 8.10.2 环境运行 `gradle run`。实验中的 `direct` 场景留下空结果，`self` 场景保留 `created`。

这个差异支持的是“事务拦截入口不同”，不是“运行时异常有时不会触发回滚”。只断言两个调用都抛异常，完全无法区分错误解释。再看[共享回滚](/learn/spring-service-boundaries/transaction-proxy#shared-rollback)：外层捕获异常以后，仍需要检查事务最终状态和返回时发生的异常。

## 每次实验保存六件事

1. **主张与前提**：要判断哪一条机制，版本、隔离级别、输入和资源上限是什么
2. **运行前预测**：写出正例与反例的响应、最终数据和资源状态
3. **执行入口**：使用完整源码包、明确命令和固定参数，记录源码指纹；不要只保存复制过的片段
4. **可区别的观察**：HTTP 要看状态、媒体类型和业务响应体；并发要看工作是否 join；持久化要看提交后的事实
5. **失败与清理**：记录故障注入点、退出码、超时和资源释放。清理失败也应使实验失败
6. **结论范围**：说明结果支持什么、未运行什么，以及换数据库、协议或平台后需要重验的条件

记录一个反例被测试识别的结果。可以暂时把响应体改错、移除一次 join，或打断共同事务边界；测试应在对应合同上明确失败。完成后恢复正确实现并重跑相关检查。

## 各路径的运行入口

| 实验 | 入口 | 证据边界 |
| --- | --- | --- |
| [Spring 服务边界](/examples/spring-service-boundaries.zip) | README 中的生命周期、HTTP、连接池实验 | 对象事件、回环请求与 H2 资源行为；不代替目标数据库锁实验 |
| [Spring 事务代理](/examples/spring-transaction-proxy.zip) | `gradle run` | 十个 Spring/H2 事务场景；不代表跨线程或分布式事务 |
| [Go context](/examples/go-context-cancellation.zip) | demo、test、race、vet | 标准库、虚拟时间和内存副作用；不代表真实数据库取消 |
| [Go 服务生命周期](/examples/go-service-lifecycle.zip) | `verify.sh` | 回环 HTTP、并发和真实 main 子进程；信号结论限定到记录的平台 |
| [数据一致性](/examples/data-consistency.zip) | `python3 check_static.py` 后 `bash run.sh all` | MySQL/Redis 的真实服务场景；静态检查不等于服务通过，受控接收端不等于真实 broker |

先阅读包内环境与清理说明，再运行。首次解析依赖或拉取镜像需要网络；不要将实验脚本指向现有业务实例。示例数据、错误处理与资源限制服务于明确的学习问题，不能直接当作生产配置。


::: info 2026-10-02 的后续验证记录
下载包保持冻结源码的原始指纹，包内 README 与 RESULT-CONTRACT 中的 NOT_RUN 是冻结时状态。该精确快照随后在 [GitHub Actions 第 36991587537 次运行](https://github.com/weilhuang/wiki/actions/runs/36991587537)完成全部二十三项真实 MySQL/Redis 场景，并经过独立证据复核；[持久验证摘要（JSON）](/examples/data-consistency-verification.json)记录源码、镜像、结果与清理。三次主动终止连接后的有界关闭警告如实保留。这次验证仍不覆盖真实 broker 或生产环境。
:::

## 如何评审一个设计

先要求作者画出提交点、响应点与资源所有者，再逐项检查失败矩阵。每行都应回答：调用方知道什么，数据库已经做了什么，哪些工作还未结束，重复执行会怎样，以及谁负责恢复。

随后提出一个相反方案。例如长事务便于保持局部原子性，但等待下游时可能延长连接持有；短事务缩小持有期，却需要显式处理提交后的响应失败和重试。评审应说明取舍条件，而不是把某一种做法写成无条件规则。

最后检查证据能否支撑措辞：“源码显示”“受控实验通过”“真实回环 HTTP 通过”“生产容量已验证”是不同强度的结论。更高层环境未测，应列在剩余工作中，不能用低层 PASS 替代。
