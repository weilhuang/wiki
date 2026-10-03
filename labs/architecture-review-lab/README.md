# 模块边界与订单取消评审

A-r3沿用环境替换后的r2重建底稿，不声称与丢失r1字节相同。r2独审HOLD：三项坏实现曾通过旧公开套件。r3补齐完整状态oracle并重新取得执行结果、源码和制品哈希；旧结果不作当前通过证据。全部输入为合成设计条件，无生产数据、真实账户或凭据。

## 运行

已运行CPython3.12.14/Linux，标准库。无需安装、线程、服务、监听或网络。原补丁重检入口会创建有限Python子进程。在本目录运行：

```sh
python3 --version
timeout 10s python3 -B walk_boundaries.py
timeout 10s python3 -B walk_review.py
timeout 10s python3 -B verify.py --output local-results.json
```

没有timeout的系统可用已有执行器设10秒外层上限。程序自身有限且不等待。完整验证输出19个正确场景、19个目标拒绝、6类无关结果拒绝，退出0。

```sh
timeout 10s python3 -B verify.py --mutant split-local-commit
timeout 10s python3 -B verify.py --mutant ignore-surge
timeout 10s python3 -B verify.py --mutant repeat-release
```

单个指定反例实际退出2并输出target-rejected。必须同时核对异常类型、断言身份和完整expected/actual；启动/语法错误、错误断言、同身份但错误状态或静默成功不能冒充通过。

新增三个独审目标，可分别运行 `python3 -B verify.py --mutant async-abort-only-half-commit`、`--mutant revoked-replay-only-side-effect` 和 `--mutant completed-outbox-rollback`，预期都是精确目标拒绝、退出2。`source_mutations.py`只把review_regressions中三个固定原补丁应用到内存副本；模型原文件不变。补丁语法/上下文/编译错误会失败，不能计作目标拒绝。每个原最小探针也随源码交付，可用 `python3 -B review_regressions/<name>.py .` 检查正确模型。

也可运行 `timeout 30s python3 -B run_review_regressions.py --output local-review-results.json`。它使用可自动清理的源码副本，逐项运行原审阅者最小探针、应用原.patch，再运行默认公开verify.py与原探针：正确模型的探针必须exit0，破坏后的公开套件及探针必须exit1并逐值匹配指定失败。补丁或运行不能启动不算通过。此过程仅临时文件和有限Python子进程，无服务、网络或安装。

## 源文件与独立预期

boundaries.py只查显式模块引用及写表声明，不扫描应用；漏填边不会被发现。review_model.py包含当前授权、期望版本、共同提交、PENDING交接、释放凭据、去重、水位、回退与预算。walk文件是正文完整代码。verify.py安排有限刺激并检查状态副作用。

expected_states.py只由独立literal夹具和明确期望状态构成，不导入/运行待测实现；mutant-oracles.json是其固定数据副本，静态检查二者相等。改变预期需要独立复核，不能重录待测输出使测试变绿。source-manifest.json固定所有源码与输入；实际结果单独提供，不进入源码ZIP。

## 模型边界

每次方法顺序执行；deepcopy后替换状态被假定不可分割，不证明真实数据库事务。主体、成员、授权、时间、事件和token是可信夹具，没有签名、身份供应商或服务认证。成员和版本变化只在明示步骤发生，未模拟并发check/use。

每租户只有一个库存单位，由本租户o1预留；释放使可用量0变1。每订单一份预留、一生一次取消。没有创建、履约、退款、删除重建或跨仓。事件身份含租户/订单/版本，回执匹配该范围。模型ack只是列表，没有broker或持久磁盘。

fencing只在资源已见高代次后拒绝旧代次，不实现可信授予。重复同事件返回旧事实不代表同token任意新命令安全。保守回退检查拒绝v1接管新PENDING/Outbox责任，不实现归档或真实回退。SLO仅已分类合成计数，不实现28天窗口、真实入口采集或30秒成熟队列。静态池预算不推出容量或延迟。

not-run：Java/Spring/Modulith、Go、MySQL、broker、网络、真实token协调器、IdP、Kubernetes、生产SLO、容量、真实迁移/恢复、全站CI/部署/浏览器。其他站内实验只作关联。

源代码和教学材料原创、MIT许可。第三方网页只有链接，其版权不由MIT覆盖。
