# MySQL 机制实验

这是 MySQL 8.4.7 / InnoDB 的有限教学实验源码；当前状态 NOT_RUN。SQLite、内存模型、静态解析成功都不能替代本实验。官方 MySQL 镜像仅作运行依赖，不打包其代码或镜像；本目录原创教学应用代码按 MIT 授权。安全封装参考现有站点实验，但独立文件、独立结果、独立证据，不继承旧包验证结论。

## 运行入口

由独立审核通过的公共仓库 Ubuntu 24.04 pull_request runner，在全新 checkout 内执行：

```sh
python3 -B labs/mysql-mechanisms-lab/check_static.py
timeout --kill-after=15s 12m python3 -B labs/mysql-mechanisms-lab/run.py
python3 -B labs/mysql-mechanisms-lab/collect.py "$RUNNER_TEMP/mysql-mechanisms-evidence"
```

run.py 拒绝非 GitHub Linux runner；不能据此推断任何 GitHub job 都被授权。workflow 必须只用 contents:read、标准公共 runner、无 credentials persistence、无 secrets / environments / deployment，且源清单须先由独立审阅者接受。已有 results 会导致拒绝，以免混入旧记录。运行需要 GitHub runner 自带 Docker Compose、Python 和可拉取的官方 mysql:8.4.7；不安装包。

36 行 orders 加 2 行 inventory。一个随机 project、一个 MySQL、1 GiB、1 CPU、256 pids、内部网络、无主机端口或绑定挂载。只有一次启动；正常、三个真实语义变体和一个 SQL 语法归因控制依次运行。三个长期 mysql CLI 是 observer、A、B 的三个实际服务器连接，最大同时3个实验长连接（健康检查可能有额外短连接）。SQL帧12秒、锁等待8秒、SELECT最大5秒；启动240秒、每进程90秒、主运行420秒，清理名义90秒加最多30秒终止宽限，明显小于外层720+15秒，workflow总时限15分钟。不是压力/性能/复制实验。

## 断言与失败分类

baseline 必须完成 index_cases、begin_is_not_snapshot、rr_retention、rc_refresh、current_and_own、lock_handoff。分别断言实际行集/值/ROW_COUNT/提交后外部可见性/回滚后的外部状态。锁等待屏障读取 performance_schema 的等待者和持锁者连接 ID；轮询间隔不是顺序证据。

- mutant-missing-tenant：真实查询去掉 tenant_id 条件；仅在 index.ordinary-covering.rows 得到不同真实行集和42才算击中反例
- mutant-rc-for-rr：真实A会话改为 RC；仅 rr.repeat 的10/20与11/21不符和42才算击中
- mutant-stale-write：真实UPDATE写10-2常量；仅 own.mixed-view 的8/20与5/20不符和42才算击中
- control-sql-error：故意 SELEC，必须归类 SQL_FAILURE/43/1064；不计作语义反例
- 超时44、基础设施45、客户端清理46、容器清理失败都使整轮失败；不能抵消为 mutation 成功

--force 只让 mysql 客户端在 SQL 错误后返回帧结束标记；driver仍把每一条 ERROR 转成失败。禁止优化 Python 对断言的影响：业务断言用显式判断，没有 Python assert。会话关闭显式ROLLBACK、检查客户端退出；最后只 down 自己的 project 并验证其容器、卷、网络均消失。SIGKILL/runner硬终止无法保证 finally 执行，因此外层时限预留清理预算。

## 产物

results/<随机owner>/ 绑定源码manifest SHA、合并checkout SHA、PR头/基线SHA、run ID/attempt、服务器VERSION、镜像image ID/RepoDigests、完整SQL帧和顺序屏障、原始JSON执行计划/ANALYZE树、断言expected/observed、退出与清理状态。源码manifest包含本目录除自身和results外每个文件，逐字SHA256。

每文件最多1 MiB，trace最多512 KiB，收集器最多40文件/8 MiB，拒绝symlink和未列入类型的路径。只上传此轮目录，不上传工作区、环境、Docker inspect整对象、数据库卷或credentials。artifact只留3天。SQL与固定数据无个人数据或秘密。公共教材摘要后续另外绑定这轮身份；源码ZIP不会夹带执行日志。

普通无hint计划与FORCE INDEX计划都保留，不预先断言普通计划必须选某个索引，也不把一次耗时作性能排名。EXPLAIN ANALYZE真的执行隔离数据上的SELECT。人造约束计划用于观察结构，不代表优化器自然偏好。

## r2 安全修订

r1静态检查曾通过，但独审纯Python对抗检出了路径祖先、伪PASS、部分构造清理与总预算缺陷；不删除失败历史，也不将这种纯控制流检查称作MySQL执行。r2严格核对所有祖先无symlink、目的地仅新建RUNNER_TEMP/mysql-mechanisms-evidence、当前源树与CI身份、全模式/SQL帧/连接/断言/计划/退出/清理。失败诊断单独标VALIDATED_FAILURE_DIAGNOSTIC，绝不作为通过证据。任何缺少必须字段的PASS都拒绝上传。构造失败和每个关闭异常均不跳过其他已建连接；版本不匹配归基础设施45。

## r3 安全修订

r2关闭r1全部已知对抗项后，独审又检出空业务trace伪PASS、失败诊断未绑定日志、校验后symlink替换与新增manifest未计入预算。r3逐项保留这段失败历史。完整baseline要求39个固定业务断言及其实际会话SQL响应，三变体要求精确改变后的真实值，不接受任意X/Y；语法控制须实际对应SELEC帧。计划绑定原始EXPLAIN响应，不接受空query_block。所有诊断事件采用字段白名单。

源及证据用逐层目录句柄O_NOFOLLOW读取，上传文件从验证过的同一字节写出，不再从易变化路径copyfile；最终树再校验并把两个manifest计入40文件/8MiB。命令记录规范化argv/SHA、有效时限、实际退出与启动错误/超时/中断分类、日志SHA。CI身份绑定repository/ref/event/workflow_ref以及当前workflow源SHA；镜像记录平台。收集器再次核对实际git HEAD与原运行身份。只有从精确审查源码和对应GitHub run取得的产物可称真实运行证据；这些检查不是数字签名，也不能独自证明任意第三方提供的完整虚构日志来自数据库。

## r4 完整协议修订

r3独审确认完整正向五模式记录能被接纳，但仍能删除事务设置/开始帧或把close移到最前；另有FIFO在类型检查前阻塞。r4保持39条值断言不变，增加逐case完整客户端协议：初始化与open、隔离级别、START/显式快照、首次读、B提交ack、当前读/写、COMMIT/ROLLBACK和最后三次close必须按精确顺序出现；唯一可变重复是有界锁COUNT轮询，须0…正数且绑定连接。缺失/错级别/乱序不能通过。secure_read最终文件用O_NONBLOCK打开，再fstat拒绝非regular。

作者11项控制流回归通过；另借独立审查的合成完整响应夹具验证五模式继续接纳、删除事务/commit/rollback、改隔离及前置close均拒绝（17个验证器控制）。这些是日志验证器的控制检查，不是MySQL运行结果；不把合成夹具打包成DB证据。
