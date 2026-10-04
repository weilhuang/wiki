# AppService：API、缓存与收敛实验

一个 AppService 管理同一命名空间、同名的 Deployment 和 ClusterIP Service。六篇文章共用这一份源码。普通无状态服务可以直接写 Deployment/Service；本实验是在教学 API 里集中 image、replicas、运行约束和观察状态，随后检查控制器为这种约定承担的责任。

这是 P3 的独立源码身份。它复用已发布最小通道的实现模式，但所有新增源码的 Go、envtest、kind 和生成器结果在首次执行以前均为 NOT_RUN，不能继承旧源码的通过记录。不要用本文替代某次运行的 source_id、完整结果和清理记录。

## 固定环境

Go 1.27.1，controller-runtime v0.25.2，Kubernetes Go 模块 v0.37.0，controller-tools v0.22.0，envtest/kubectl v1.37.0，kind v0.33.0。

kind 节点固定为 kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5。官方工具 URL 与摘要在仓库 scripts/ci/controller_path_versions.json；没有 latest、registry push、真实凭据或付费集群。

## 分清四层证据

| 层次 | 本包检查 | 不能推导的结果 |
| --- | --- | --- |
| Go 单元 / fake client | 受控字段、owner 拒绝、重复操作、局部冲突及身份防线；真正的 client-go 普通队列算法 | API 默认值、真实冲突或真实 workload |
| 纯 Python | Ready 判断器；完整库存缺项、错误身份、时间和清理边界的拒绝 | Go 已执行或 Kubernetes 已启动 |
| envtest + API server | schema/CEL/default/prune/status、UID/list/watch、冲突、实际 informer/manager/queue；人造 Deployment status 仅是输入 | kubelet、Deployment 控制器、DNS、HTTP、GC |
| 单节点 kind | 真实非 root Pod、Service DNS 的精确 HTTP 合同、scale、漂移、删除重建、manager 重启、NotReady 恢复、foreign 保留、RBAC Forbidden、owner GC | 生产容量、多节点网络、容器逃逸防护、全业务依赖健康、leader election、webhook |

详细库存见 test-inventory.json。正确的进程退出还不够：全部必需测试和子测试必须各有通过结果。缺项、重复、跳过、编译失败或超时不能当作语义反例通过。

## 从源码到预期

- API：api/v1alpha1/types.go；image 必填且 1–256 字符，replicas 默认为 1 且只允许 1–3，名称用 CEL 限制为可兼容 Service 的 DNS label
- 控制器：internal/controller/reconciler.go；watch/cache 提供键，实际 Get 使用未缓存 APIReader，写入采用带 resourceVersion 的乐观锁 merge patch
- 所有权：同名但没有当前 AppService UID 的 controller ownerReference 时拒绝接管；已拥有但 selector 不兼容时拒绝删除重建
- 字段：管理 replicas、selector、模板 labels、整个 containers 列表、Pod securityContext 和 token 挂载约定；保留其他字段以及 Service 的 ClusterIP/ClusterIPs/IPFamilies/IPFamilyPolicy。这里不保证保留任意 sidecar 或 admission 改写
- 状态：创建成功仍为 Progressing；只在 Deployment 当前 generation、精确副本统计和 Available 条件满足时写 Ready。它不取代集群内 HTTP 断言
- 身份：写 status 前重新读取；UID、generation 或删除状态变了就丢弃这次旧观察。相同 status 不反复写入
- 重试：普通错误交给框架按键退避；显式指数 limiter 是 200ms 到 10s，没有额外的全局令牌桶。OwnershipConflict/InvalidChild 使用 10s 定期复查，未返回 TerminalError

v0.25.2 的 manager 默认使用 controller-runtime 自己的 priorityqueue。TestClientGoQueueKeyCoalescing 刻意选择 client-go 普通队列，只说明那条算法；ManagerTransientErrorRetry 则保留框架默认队列，用测试包装器在第一次 APIReader 调用前返回一个错误，观察 When(该键)=200ms 和随后的真实 API 写入。这个故障注入不进入生产 manager。

## 本地检查

从本目录执行。先提供精确版本 Go 和所需依赖；常规开发环境首次可用 go mod download，之后保持 -mod=readonly。模块缓存只作为依赖来源，不是运行结果。

```sh
go version
GOTOOLCHAIN=local GOENV=off GOWORK=off go mod verify
GOTOOLCHAIN=local GOENV=off GOWORK=off GOMAXPROCS=2 CGO_ENABLED=0   go test -mod=readonly -trimpath -p=1 -json -count=1 -timeout=150s   ./api/... ./internal/controller/... ./cmd/operand/...
python3 -B scripts/check_kind_oracle.py --source-id local-synthetic-check
```

生成器在临时副本内重生 CRD/DeepCopy，逐字对比提交文件；语义变体也只改临时副本。正式结果必须用受审源码清单生成的身份，不能使用下面的示例标签替代。

```sh
python3 -B scripts/check_generated.py --source-id local-generator-check
python3 -B scripts/check_mutants.py --source-id local-mutant-check
```

变体分别移除 Deployment 所有权防线、去掉 rollout generation 检查、去掉写 status 的 UID 检查、清空平台分配的 ClusterIP。每个变体先运行同一精确测试的正确版本，再要求坏版本以正常测试失败退出，并命中特定断言。编译错误和未运行测试不算拒绝了坏行为。

## envtest 与 kind

只编译 API 测试，不启动 TestMain：

```sh
go test -mod=readonly -trimpath -p=1 -c -tags=integration   -o /path/to/private-output/integration.test ./test/integration
```

真实 envtest 执行必须显式提供 P3_ENVTEST=1、P3_SOURCE_ID、未存在的 P3_ENVTEST_REPORT 和已校验的 KUBEBUILDER_ASSETS 绝对路径。不要用 -run '^$' 充当 compile-only：TestMain 仍会启动 API server。测试会停止 manager、显式删除自己命名空间里的夹具并停止 control plane；envtest 没有 namespace controller/GC，删除请求不等于命名空间被 GC 完成。

仓库工作流 controller-path.yml 及 scripts/ci/controller_path_*.py 是单独的受审通道，未独立审查并获准前不执行。所有命令、源码前后身份、确切测试库存、工具摘要、退出状态及清理结果共同进入证据。真实 kind 只使用本次随机 cluster 和镜像标签；每次 kubectl 指定临时 kubeconfig/context/cache/namespace。manager 只有单命名空间 Role，cache 也单独限制该命名空间；禁止访问 Secret、另一命名空间 Deployment 与 Namespace 的断言必须实际收到 Forbidden。

kind 主工作 600 秒，另留 30 秒诊断和 140 秒清理；不足预算就在创建集群以前退出。只删除自己创建的 cluster 和两个随机镜像标签，不 prune、不删除共享节点镜像、不读取用户 kubeconfig。诊断限定本实验命名空间，每文件最多 8 MiB、上传合计最多 32 MiB、保留三天。kubeconfig、证书/密钥、Secret、token 与完整环境不上传。

## 练习

1. 连续重复 reconcile，预测哪些 resourceVersion 应保持不变，再观察 AppService、Deployment、Service 三者
2. 创建一个无 owner 的同名 Service，预测状态原因与该 Service 的 UID/spec；确认没有接管
3. 把 Deployment status 的 observedGeneration 留在旧值，其他统计全部设为 ready；解释为什么仅这一处就足以阻止 Ready
4. 在真实 kind 把 image 改成不存在的本地标签，再改回；分别记录 spec generation、Condition observedGeneration、kubelet 的 ErrImageNeverPull 与 HTTP 结果

第 3 项是 API 输入实验，不是运行 Pod；第 4 项才观察实际 kubelet 和网络。P2 完整业务服务将在后续集成时替换这里的最小 operand。此时 operand 只提供固定 JSON 和 readyz，没有数据库或认证合同。

来源见 THIRD_PARTY_NOTICES.md；章节的逐字源码片段、来源和执行边界由包级 sources.json、snippets.json、verification.json 绑定。
