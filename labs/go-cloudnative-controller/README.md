# AppService 控制器：真实 API 与工作负载的最小实验

这个教学控制器把一个命名空间内的 `AppService` 调整为同名 `Deployment` 和 `ClusterIP Service`。它用于观察 API 校验、watch/reconcile、资源所有权、状态冲突及工作负载恢复。普通无状态 HTTP 服务可以直接使用 Deployment 和 Service；本实验不把自定义 API 当作必需架构。

## 版本与验证范围

版本固定为 Go 1.27.1、controller-runtime v0.25.2、Kubernetes Go 模块 v0.37.0、controller-tools v0.22.0、Kubernetes/envtest/kubectl v1.37.0、kind v0.33.0。工具下载 URL、校验和、kind 节点镜像摘要在仓库的 `scripts/ci/go_cloudnative_versions.json` 中；不使用 `latest`。setup-envtest 仅为研究时参考，CI 直接提供校验后的 envtest 二进制。

此源码快照在 2026-10-03 的本地检查中通过了 24 项必需 Go 测试/子测试、三个包的退出检查及八项纯 Python 判断器测试。集成测试已编译，尚未在本地启动 API server。**冻结本快照时，真实 envtest 与 kind 均为 NOT_RUN**。后续 CI 结果应以具体运行的源码身份和完整产物为准；本段不是后续运行的动态状态页。

| 层次 | 能验证什么 | 不能据此推导什么 |
| --- | --- | --- |
| Go 单元与 loopback HTTP | DeepCopy、所有权拒绝、受控字段、冲突重试、响应状态/正文/媒体类型及禁止重定向 | 真实 API 默认值、watch、Pod 或网络行为 |
| Python 判断器 | 缺失、过期、多余或未就绪副本不会被验收误判为 Ready | Kubernetes 已执行这些场景 |
| envtest + 真实 manager | API 校验/default/status/conflict、watch 与重启收敛 | envtest 没有内置工作负载控制器；手动写入的 Deployment status 不证明真实 Pod、Service 流量或 GC |
| 单节点 kind | 实际 Pod、Service DNS 内 HTTP、漂移修复、子资源重建、manager 重启、owner GC、RBAC 拒绝和清理 | 多节点、生产容量、云厂商网络、升级、leader election、webhook 或最终用户安全 |

## 本地单元检查

从本目录执行，先准备精确版本 Go；首次模块下载需要正常网络。

```sh
GOTOOLCHAIN=local GOWORK=off go version
GOTOOLCHAIN=local GOWORK=off go mod download
GOTOOLCHAIN=local GOWORK=off go mod verify
CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off GOMAXPROCS=2 GOMEMLIMIT=512MiB \
  go test -mod=readonly -trimpath -p=1 -json -count=1 -timeout=150s \
  ./api/... ./internal/controller/... ./cmd/operand/...
python3 -B scripts/check_kind_oracle.py --source-id local-synthetic-check
```

必需用例名在 `test-inventory.json`，不能只看进程返回 0。缺失、重复、跳过或失败的必需测试不能算通过。Python 命令的 `source-id` 是本地示例标记；正式 CI 使用整个受审源码清单的摘要，不能拿该示例标记冒充绑定证据。

只编译集成测试时，使用新建的私有输出目录：

```sh
go test -mod=readonly -trimpath -p=1 -c -tags=integration \
  -o /path/to/private-output/integration.test ./test/integration
```

不要用 `-run '^$'` 代替编译检查：此包的 TestMain 仍会启动 envtest。真实执行需要 `P0_ENVTEST=1`、精确的 `P0_SOURCE_ID`、尚不存在的 `P0_ENVTEST_REPORT` 和经过校验的 `KUBEBUILDER_ASSETS` 绝对路径。独立 CI 包装器负责这些输入、最长运行时间和子进程回收。

## 控制器处理的对象

`lab.wiki.example/v1alpha1` 的 `AppService.spec.image` 必填，`replicas` 默认为 1，只允许 1–3。名称必须能用于同名 Service。状态使用独立子资源，记录 `observedGeneration` 与 Conditions。

manager 必须指定命名空间，缓存和 Role 限制在该命名空间；单 reconcile worker、不启用 leader election。写入前使用 APIReader 取得当前对象，受控字段用乐观锁 merge patch 更新，保留 Service 分配的 ClusterIP、IPFamilies 等字段。旧观察不能冒充新 generation 的 Ready。单次 reconcile 有 10 秒上下文；状态冲突最多尝试三次，队列错误退避最多 10 秒后仍可继续恢复。

同名但无当前 AppService controller ownerReference 的子资源会被拒绝接管。Deployment 不兼容的不可变 selector 也不会通过删除重建来掩盖。新子资源使用同命名空间 ownerReference，`blockOwnerDeletion=false`；controller 不直接删除它们。只有真实 kind 的 GC 用例能证明 Kubernetes 完成级联清理。

实验容器使用由本模块编译的 scratch 镜像、非 root 身份、只读根文件系统、移除 capabilities、资源限制和显式 readiness probe。operand 与探针 Pod 不挂载 API token，镜像只装载到本次 kind，`imagePullPolicy=Never`。这不是通用镜像分发或多租户执行接口。

## CI 执行与清理

仓库工作流 `go-cloudnative-bootstrap.yml` 在标准公开 Ubuntu runner 上执行。源码清单包含本目录及包装器、版本表和 workflow；前后摘要必须相同。envtest 的六个场景与 kind 的十四个场景分别记录，不把编译失败、启动失败、超时或遗漏场景算成反例通过。

kind harness 先确认随机 cluster 名称和两个镜像标签不存在，再创建本次资源。每次 kubectl 都显式指定临时 kubeconfig、context、私有 discovery cache 与命名空间。HTTP 用例从集群内的短命 Pod 访问 Service DNS，要求精确 200、JSON 正文和媒体类型；302 跳转即失败。RBAC 用例以 manager 身份实际请求 Secret、另一命名空间 Deployment 与 Namespace，要求 API 返回 Forbidden。

主工作最多 600 秒，随后保留 30 秒诊断和 90 秒清理。失败路径也尝试删除本次 cluster 与两个生成镜像标签，检查不存在，并移除临时 kubeconfig。不会执行 Docker prune、删除共享节点镜像、读取用户 kubeconfig 或推送 registry。包装器在开集群前检查工作流剩余预算，不够就退出。

只收集有限的版本、命令结果、manager 日志和本实验命名空间资源。每文件最多 8 MiB，总共最多 32 MiB，保留三天。Secret、token、kubeconfig、证书/密钥内容、完整环境与广泛主机日志不进入上传目录；上传必须经过逐文件检查，清理或诊断失败会使最终结果失败。

## 生成代码与来源

API/控制器/测试为原创教学示例。CRD 和 DeepCopy 来自固定版本生成器：

```sh
go run sigs.k8s.io/controller-tools/cmd/controller-gen@v0.22.0 \
  object crd paths=./api/... output:crd:artifacts:config=config/crd
```

生成后应对比已提交文件；不要为通过检查静默修改依赖。上游声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。机制依据包括 [controller-runtime v0.25.2](https://github.com/kubernetes-sigs/controller-runtime/tree/v0.25.2)、[envtest](https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.25.2/pkg/envtest)、[乐观锁 patch](https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.25.2/pkg/client#MergeFromWithOptimisticLock)、[owner/dependent](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/) 与 [kind v0.33.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0)。
