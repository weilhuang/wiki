# 数据一致性：真实服务实验候选

状态：NOT_RUN。只有静态检查已执行；没有 MySQL、Redis 或真实 broker 通过记录。

## 前置条件与唯一入口

需要 Linux、Bash、GNU coreutils timeout、Python 3.11+ 标准库、官方 Docker Engine 与 Compose V2。实验不安装这些工具；无 Docker 时请使用获准的标准 CI runner。执行前审查本目录脚本。仅从本目录执行：

```sh
python3 check_static.py
bash run.sh all
# 或独立一章，脚本每次新建完全隔离的服务/数据
bash run.sh d1
bash run.sh d2
bash run.sh d3
bash run.sh d4
bash run.sh d5
```

镜像只从 `infra/versions.env` 读取：MySQL 8.4.7；Redis 7.4.7（Alpine 3.21）。该文件是已有课程版本台账的逐字节快照，SHA256 为 `633dd50e7da950a0da9ddb86484e11a63b475a82c89688c3a8f2640c24568a4b`。含其他课程镜像条目，但 Compose 只引用 MYSQL_IMAGE / REDIS_IMAGE，不下载其他镜像。镜像 tag 固定不代表不可变 digest；实际运行须保存 Docker image ID/RepoDigests。

`run.sh` 随机创建 `ks-data-<uuid>` 项目，只接受脚本产生的 owner 标签。无 host ports，内部网络；MySQL 通过容器内 Unix socket，Redis 通过容器内 localhost。空 root 密码仅用于此隔离、一次性教学容器，禁止移植到部署配置。Redis 不持久化，是可丢缓存；MySQL volume 在本次运行中持久化。程序不接收任意数据库 URL，不会连接已有数据库。

退出时先留容器日志，再执行精确 project 的 `compose down --volumes`，只移除本次实验资源；不运行 prune。SIGKILL/runner 硬中断可能跳过 trap，运行平台须清理对应项目。不要为了省空间删除别人的镜像、网络或 volume。若清理失败，`cleanup.log` 和 `exit-codes.txt` 必须一起保留。实验从不保存账号、令牌或实际用户数据。

## 编排与失败注入

- `Session` 通过 mysql CLI 保持真实连接，以随机 SELECT sentinel 划定响应；`--force` 仅为在期望 SQL 错误后捕获 sentinel，每条 ERROR 都由 Python 分支显式检查，错误事务一律回滚
- D1 两次读取完成是朴素更新的 barrier；修复路径通过 performance_schema.data_lock_waits 确认阻塞后才放行持锁者。死锁不假定哪一方成为 victim
- D2 同键冲突由真实唯一索引裁决；提交前断开用 KILL CONNECTION，提交后丢响应是调用方适配器主动丢弃结果，不是 TCP 故障或 HTTP 集成证据
- D3 delivery_receipts 是真实 MySQL 持久化的可控接收替身，独立连接提交；不是 Kafka/RocketMQ。relay/consumer 的发布后/提交后中断由控制流故障注入，提交前消费中断会终止独立数据库连接
- D4 通过显式 SQL/Redis 调用次序暂停回填；并发回填用 threading.Barrier；失效丢失是抑制一次命令，不冒充 Redis 宕机或 failover。过期通过 EXISTS 谓词等待，不把固定 sleep 当作证明
- D5 在同一数据集叠加重复请求、未知结果、重投、消费中断、陈旧负缓存和重放。迁移单独验证 v1/v2 完整快照的兼容与乱序，不能外推增量事件

## 输出与成功门槛

每次 `results/<uuid>/` 包含 result.json、trace.jsonl、环境版本、镜像身份、容器日志、异常和回滚/清理日志。PASS 必须同时满足：进程 0 退出；请求章节所有 case PASS；真实版本吻合；negative control 被识别；容器日志与 ps 证据采集、scoped cleanup 的退出码都为零。shell 最终完成阶段才把实际退出码写入 result.json；Python 的“cases passed”仅表示用例阶段完成。执行入口拒绝 Python 优化模式，全部必需检查采用显式 require/raise，完整 case 清单不允许缺项或重复。`result.json` 只显示所选章节，不把 d1 通过等同 all 通过。

各章 case 清单和预期见 `RESULT-CONTRACT.md`。日志中的 SQL、行数、connection_id、等待边、重复投递与最终联合查询是原始证据。不要以“没有 ERROR”代替不变量检查。静态检查只检查文件/语法/安全约束，绝不证明 SQL、Lua、驱动、容器或时序正确。

## 简化与生产差距

本项目是可执行反例与协议实验，不是生产订单服务：无 HTTP、鉴权、SQL 驱动连接池、真实 broker、复制、故障切换、机器掉电、磁盘故障、吞吐或 p99 测量。所有业务/操作/事件身份测试值限定为规范化的小写 ASCII；schema 的 VARCHAR 继承 MySQL 默认排序规则，未验证大小写敏感或任意 Unicode 身份。生产必须明确选择二进制/大小写敏感比较或规范化规则，并为键等价性补测试，不能把当前 schema 当通用幂等身份规范。order business_id 在实验由调用方稳定给出；终态 rejected 按保存结果重放。relay 单进程，未实现 lease/多 worker 抢占；consumer 的本地去重不能保护外部发货/收费。库存守恒只覆盖预留、没有取消/补货并发。跨库独立部署要补网络与恢复测试。

所有新实验在真实环境通过并经独立复核之前，知识站章节维持 draft，不能标记路径已完成。
