# 来源与身份

全部正文是中文转述与原创分析，没有重分发上游实现源码。

- Kubernetes v1.34 官方文档快照：probes、Pod lifecycle、container lifecycle hooks、EndpointSlices、Service proxies、Deployments；2026-10-03 实际核对。版本网站称为静态快照，URL 不声明为 commit 级字节不可变
- Kubernetes 固定 tag v1.34.0：[podToEndpoint](https://github.com/kubernetes/kubernetes/blob/v1.34.0/staging/src/k8s.io/endpointslice/utils.go) 与 [CategorizeEndpoints](https://github.com/kubernetes/kubernetes/blob/v1.34.0/pkg/proxy/topology.go)；Apache-2.0 上游，仅核对相关函数，没有复制源码或冒认实现实验
- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/)：事件比例与目标/预算职责
- [Google SRE — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)：用户症状与内部原因、黄金信号
- [Grafana — RED Method](https://grafana.com/blog/the-red-method-how-to-instrument-your-services/)：2018-08-03 方法介绍
- [Brendan Gregg — USE Method](https://www.brendangregg.com/usemethod.html)：作者的一手方法说明
- [Prometheus — Histograms and summaries](https://prometheus.io/docs/practices/histograms/) 与 [Instrumentation](https://prometheus.io/docs/practices/instrumentation/)：经典累积桶、分位聚合、标签成本；动态文档核对日期 2026-10-03，不对应已运行的产品版本
- [OpenTelemetry — Sampling](https://opentelemetry.io/docs/concepts/sampling/) 与 [Handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)：采样选择与字段最小化；动态文档核对日期 2026-10-03

完整来源 ID、准确 URL 与核对范围见网站来源台账。Python/YAML 片段为原创教学示例，MIT；并不是上游代码节选，因此没有上游源码字节哈希。固定 tag 来源仅用于语义对照。
