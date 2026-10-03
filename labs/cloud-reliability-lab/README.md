# 服务目标与排空：有限模型实验

先从相应知识正文理解事件和生命周期边界，再使用本包复算。所有样本都是合成数据，没有生产日志或凭据。

## 运行

验证时使用 CPython 3.12.14 / Linux；只依赖 Python 标准库，不安装依赖，不启动线程、子进程、网络、HTTP、容器或集群。

从本目录运行：

```sh
python3 --version
timeout 10s python3 -B walk_signals.py
timeout 10s python3 -B walk_draining.py
timeout 10s python3 -B verify.py --output results.json
```

`timeout` 是验证环境已有的外层进程总截止工具，不属于 Python 包；没有它的系统需由自己的执行器设置 10 秒总上限。程序本身是有限顺序逻辑，不使用睡眠或等待。

单独观察一个坏计算：

```sh
timeout 10s python3 -B verify.py --mutant mean-ratios
```

它输出 `target-rejected`、精确断言身份与实际数值，退出 **2**。完整验证器退出 0 表示正确场景通过且每个错误变体被对应断言拒绝。无关异常、错误断言身份、不同值或意外成功不能当成目标拒绝。命令未能启动或 Python 语法错误也不属于这里的预期拒绝。

## 文件与模型假设

- `signals.py`：115 条合成记录，110 条符合范围；分子/分母、分数预算、nearest-rank、经典累积桶、固定选择偏差
- `lifecycle.py`：应用接纳、普通 ready 路由缓存、工作集合、依赖所有者、显式逻辑截止时间；每次方法调用原子完成是模型前提
- `walk_signals.py`、`walk_draining.py`：与正文清理 Code Hike 注释后的片段逐字匹配
- `verify.py`：固定正确场景与错误变体、独立预期值、精确失败归因、验证器拒绝无关结果的检查
- `pod-spec-fragment.yaml`：Pod spec 的教学片段，不是完整可部署清单；路径由应用实现，preStop 需要镜像内存在 shell/sleep；仅做来源与 YAML 语法检查
- `runtime.json`、`source-manifest.json`：运行身份与交付源码哈希；结果摘要单独交付
- `SOURCES.md`：主要官方来源、固定版本和许可证边界

`Process.startup_complete`、`delete`、`publish_endpoint`、`refresh_router` 是显式安排的模型动作，不会自行启动、调度或观察现实世界。`expire` 只改变模型状态，不发送任何信号；没有实现 kubelet 的额外 2 秒、探针、sidecar 或 kube-proxy 回退。`uncertain` 表示强制结束时不能由本模型证明成功，绝不表示真实业务一定没提交。

未验证：生产 SLO、统计置信区间、抓取缺失与重置、概率采样器、监控查询、Kubernetes、真实路由传播、HTTP 协议关闭、进程信号、持久化、网络分区、生产容量。原有 Go 进程实验的结果不属于本包的新运行。

## 复核要点

1. 检查分子与分母属于同一边界，排除条件先于结果定义
2. 检查百分位不能普通平均或按事件数加权平均；累积桶是相同边界的计数相加
3. 检查零流量与数据未知分别保留，不填 100%
4. 检查端点发布、路由刷新、应用停止接纳是不同动作；已有连接路径也要受接纳控制
5. 检查未完成工作不先释放依赖，重复操作不重新开门，hook 不重置外层宽限

源代码为原创教学实现，采用 MIT 许可证。没有复制 Kubernetes、Prometheus 或 OpenTelemetry 实现源码。
