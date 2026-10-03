# 库存预约教学服务

HTTP/Gin 与 gRPC 共用 domain.Service，database/sql 与 GORM 是可选仓储。所有真实持久化验收只接受 MySQL 8.4.7，不用 SQLite、fake driver 或内存仓储替代。G07 的假 stream 单元测试只验证 Send 错误传播。

## 已执行范围

依赖解析、官方 proto 生成、Go 编译与 G07 适配单元有独立记录。真实 MySQL、TCP、进程信号、COMMIT 响应丢失和语义变体在首次源码审阅时为 NOT_RUN；编译不能扩大成系统执行。最终状态请读配套 verification 记录及源文件 SHA256。

## 固定工具与依赖

Go 1.27.1；Gin 1.12.0；gorm 1.31.2；gorm-mysql 1.6.0；go-sql-driver/mysql 1.10.1；grpc-go 1.84.0；protobuf-go/protoc-gen-go 1.36.11；独立模块 protoc-gen-go-grpc 1.6.1；protoc 36.2。go.mod/go.sum 锁定实际MVS依赖。生成文件已提交，常规构建不要求安装 protoc。

本例只用 Gin JSON，所有命令固定 `-tags=nomsgpack`。`-buildvcs=false` 避免源码ZIP在外层Git目录中受到VCS stamping影响；源码身份使用逐文件SHA256记录，不能把该选项解释为不需要来源证明。

## 本地启动

先准备自己的临时 MySQL 8.4.7 和空 schema，把连接信息通过环境变量 MYSQL_DSN 提供。不要把真实生产DSN、密码或账户数据放进源码或日志。本程序不会创建数据库，也不会替你申请权限。

运行 `sh scripts/reader-commands.sh build` 生成 out/reservationd。运行 `sh scripts/reader-commands.sh migrate` 只对当前空 schema 应用 migrations/001_init.sql，然后退出。迁移不是幂等建表器；重复执行应报错，不能悄悄接受旧表定义。用自己的数据库管理工具显式插入教学商品，例如 sku=book、stock=10，再运行 `sh scripts/reader-commands.sh serve`。

默认 HTTP_ADDR=127.0.0.1:8080、GRPC_ADDR=127.0.0.1:9090，STORE=sql。STORE=gorm 使用同一schema合同。需要容器监听地址时，显式设置地址并设置 ALLOW_INSECURE_TEACHING_NETWORK=yes；这承认本例的明文教学身份可被同网络调用者使用。此开关不提供TLS或身份认证，后续容器演示必须放在隔离教学网络。

## 健康与关闭

启动先Ping数据库并探测显式schema列，失败会退出；它不会自动迁移。GET /live 返回进程活性；GET /ready 在短预算内Ping数据库，并在开始关闭时返回不就绪。数据库失败不能由/live代替。HTTP/gRPC数据入口使用2秒服务端预算，客户端更早deadline不会被延长。

SIGTERM或SIGINT先撤销ready，然后同时关闭HTTP/gRPC的新请求入口，并在SHUTDOWN_GRACE窗口内等待已接纳调用（默认5秒，合法范围50ms..30s）。超时强制关闭，进程非零退出。进程等待自有serve/stop goroutine，再关闭数据库池。调用context不直接绑定信号，避免收到SIGTERM就提前取消原本应排空的请求。

## 教学API

公开身份是 Bearer lesson-writer、Bearer lesson-reader、Bearer lesson-other；它们是注入的测试主体映射，完整权限见contract.md，不是凭据或生产登录。

POST /v1/reservations 接收operation_id、sku、quantity。GET /v1/reservations/:operation_id 按当前主体查询。gRPC ReservationService 提供 Reserve、Get、有限 List；接口位于 api/reservation/v1/reservation.proto。错误体、拒绝順序、JSON严格规则与库存不足后的幂等结果见contract.md。

默认只支持应用自身创建/读取预约，不提供商品删除和库存管理API。operations.sku没有外键；增加商品删除、外键或其他写入口时必须重新审视锁顺序与事务重试，不能假设当前并发证明仍成立。

## 运行验收

`sh scripts/reader-commands.sh unit` 仅运行 G07 适配单元。`sh scripts/reader-commands.sh integration` 需要 RESERVATION_MYSQL_ADMIN_DSN 指向自有临时MySQL管理员入口，RESERVATION_BIN 指向已构建程序；缺失配置会失败，不跳过。管理员权限用于创建随机自有schema、读真实锁等待和按已观察connection ID断开测试连接。测试不能指向共享生产数据库。

矩阵共58个集成叶用例（其中P03是同进程Runtime+真实MySQL，P04是真实子进程强退）加1个适配单元用例，按两仓储运行的用例分别计入。每次独立创建并删除自己的随机schema，最终读取使用独立观察连接。D09只丢失一次COMMIT成功响应；G06的慢消费者取消使用受控发送屏障，不宣称测到任意网络窗口、吞吐或内存上限。

scripts/verify_results.py拒绝缺用例、skip、重复、空执行、失败和错误版本。scripts/mutants.py只接受默认入口指定语义断言失败；构建错误、panic、超时和服务缺失不能算检出。scripts/run_ci.py是待独立审阅的标准public Actions方案，仅在明确放行的workflow中运行，不由作者本地触发。CI固定官方MySQL摘要、动作SHA与资源范围，清理只涉及本次随机名称和所有权标签，不执行prune。


## r2 验证器与执行预算

每个语义变体固定目标package及完整叶集合。Go测试用结构化SEMANTIC_ASSERT记录唯一失败原因；fixture清理错误、父层自有断言、额外叶、缺失/重复包终态都阻断判定。M06是适配单元变体，其通过不能扩大为真实传输验证。

标准public runner的job上限25分钟，第一步记录job开始时间。run_ci.py内部最多650秒，其中正常工作最多530秒、清理90秒、最终记录15秒、余量15秒；外层655秒TERM和最多5秒KILL确保整次脚本不超过660秒。collect和upload分别有1分钟、2分钟界限，并由整job余量校验保护。protoc下载在独立可终止进程组内，拥有40秒墙钟预算。

普通日志最多占24MiB；另留8MiB给清理与最终证据。诊断、容器删除和网络删除独立尽力执行，任何错误累积为失败。缺失判据分别匹配本次准确容器/网络名，任意非零或无关No-such错误都不证明资源不存在。独立collector分别累计raw/public实际总量，各自不超过32MiB；上传只包含脱敏副本。
