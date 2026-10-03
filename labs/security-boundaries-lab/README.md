# Security boundaries lab r2

原创教学模型，MIT。中文正文分别解释会话/令牌信任边界与订单对象授权。

## 前置条件与边界

TrustedIdentity 与 VerifiedClaims 都是测试夹具，必须被理解为可信适配层已经完成密码学/凭据验证后的输入；Python 数据类型本身不能阻止伪造，不能暴露构造器给请求正文反序列化。本包不提供认证适配层、不接受真实凭据，不是完整身份系统。

订单、成员关系和委托是服务端受信的当前事实；请求 tenant/order_id/action 不受信。内部处理器再将动作绑定为 read 或 update-note。采用单进程顺序模型，commit 内重查与写入的原子性是假设，不是数据库锁或分布式事务的实测结论。准备结果是内部对象，提交仍重查当前事实。

采用明确的业务策略：租户成员中的当前 owner 可读和改备注；一跳委托只读，必须匹配接收者、租户、对象、当前 owner、ownership_epoch、有效期和撤销状态；归属每次变化都终止旧委托。transfer_fixture 只代表受信测试事件，不是公开转移接口。没有客服、管理员、链式委托、列表分页、财务字段、支付或生产账号。

## 运行

已执行版本 Python 3.12.14；没有外部依赖或锁文件，runtime.json 固定实测环境和运行范围。命令在本目录执行：

```sh
python3 -B walk_session.py
python3 -B walk_authorization.py
python3 -B verify.py
python3 -B verify_mutants.py
python3 -B verify_regressions.py
```

-B 禁止产生 Python 字节码缓存。正常脚本退出 0。verify_mutants.py 为每个坏实现启动一个有限子进程，单个子进程最多 5 秒；没有后台进程、端口、网络请求或真实时间等待。子进程的预期退出码为 3，且 JSON 的 assertion 必须精确等于 WRONG_ALLOW:<name>；启动失败、崩溃、超时、stderr 或错误 JSON 都会使总验证失败。单独重现一个错误允许：

```sh
python3 -B verify.py --mutant cached-allow-after-transfer
```

它应输出 WRONG_ALLOW:cached-allow-after-transfer 并退出 3，因为故意错误的提交真的写入了已经转移给 Bob 的订单。错误策略均在 mutants.py，不要用于应用代码。

records/model-results.json 保存固定矩阵的 90 个组合所产生的精确允许集合、撤销窗口及状态转移；它不是漏洞覆盖率。基线检查允许读取的正文、拒绝读取无正文、允许修改恰好一个目标订单与一个对应业务事件、拒绝修改无订单或事件副作用。records/mutant-results.json 保存每个错误实现的实际失败归因；其他 txt 为正文 walkthrough 实际输出。

## 文件

- model.py：可信输入之后的声明/会话接受模型，默认拒绝的订单策略、顺序提交模型
- mutants.py：明确错误的策略与陈旧批准写入，用于反例
- verify.py：独立允许集合、结果/副作用/状态变化断言
- verify_mutants.py：有限子进程与精确失败归因
- walk_session.py / walk_authorization.py：正文完整 Code Hike 片段的干净源码
- runtime.json / LICENSE / records/：环境、许可和脱敏结果

官方来源核对在网站内容证据中单独记录，本实验不实现 RFC 协议。未运行 Cookie、TLS、密码学、IdP/OIDC、真实会话库、网络、HTTP、数据库、缓存集群或并发。来源网页与自身测试代码都未做性能结论。

## r2 验证器修订

r1 原模型能正确拒绝下述输入，但原验证器未检测六种破坏：遗漏委托动作限制、在线校验绕过声明配置、缓存接受 inactive 或尚未观察的状态，以及提交时缺少修订号比较或递增。r2 保留 model.py 与正文 walkthrough 的原字节，补上中间状态、正文泄露与写入副作用断言。

verify_regressions.py 在六个独立临时目录中逐项修改实际 model.py，再运行同一份 verify.py。每次必须以精确的 AssertionError 及目标断言退出1；RuntimeError、语法/启动错误、意外退出0不能充当有效反例。两个提交相关变体都会在同主体的陈旧准备场景被拒绝；基线还另外检查同一准备只能成功提交一次。每个子进程有5秒上限，临时副本结束后清理。records/verifier-regressions-r2.json保存实际源变更身份与失败归因。它检验的是这六个已知缺口，不表示所有安全问题已覆盖。
