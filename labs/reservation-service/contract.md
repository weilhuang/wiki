# 库存预约服务合同 v1

冻结于 2026-10-03。此文件在源码实现前锁定验收语义；执行状态均为 NOT_RUN。

## 身份、输入与结果

教学身份映射显式注入适配器：`Bearer lesson-writer` 为 alice，可预约/读取；`Bearer lesson-reader` 为 alice，只可读取；`Bearer lesson-other` 为 bob，可预约/读取。它们是公开测试标记，不是生产凭证。默认进程只能绑定 loopback；容器教学部署必须显式允许明文教学模式。不能以此替代登录、密钥存储或多租户安全方案。

Reserve 输入只有 operation_id、sku、quantity。operation_id 与 sku 必须匹配 `[a-z0-9][a-z0-9-]{0,47}`，quantity 为 1..100。未知商品返回 not_found，不写操作。成功和库存不足均保存最终操作；同主体+操作 ID 同参数回读同状态，同键不同参数返回 operation_conflict。失败授权、输入及查询不会写入。主体不同可以使用同一操作 ID。

公开 Operation DTO 字段及顺序固定为 operation_id、sku、quantity、state；state 只为 confirmed 或 rejected。内部 subject 和数据库故障原因不得返回。POST /v1/reservations 成功为 200 application/json，精确 JSON 无末尾换行；库存不足为 409 和 out_of_stock 错误，但 GET 仍读到 state=rejected。GET /v1/reservations/:operation_id 返回 200 或 not_found。

HTTP 错误体精确为 {"error":{"code":"CODE"}}；媒体类型固定 application/json。身份→权限→媒体类型→正文读取上限→JSON形状→领域输入→仓储的顺序固定。缺失/多值/错误 Authorization 为 401 unauthenticated；无权限为403 permission_denied；非 application/json（允许 charset=utf-8 参数）为415 unsupported_media_type；正文超过1024字节为413 body_too_large；读失败为400 body_read_failed；JSON必须是单个非空对象，键只允许且要求上述三个字段，重复键（含转义等价键）、null、尾随值、浮点 quantity、未知键均为400 invalid_json；合法JSON中的非法值为400 invalid_argument。

HTTP 库存不足/操作冲突为409，not_found为404，context.Canceled为499 canceled，deadline为504 deadline_exceeded，commit结果未知为503 outcome_unknown，其余仓储错误为500 internal。499只在响应通道尚可写时可观察；客户端主动断开不保证收到任何正文。

gRPC Reserve/Get/ List 是 proto3。Reserve/Get 成功返回相同业务 payload；服务端生成的应用错误 status.message 固定公开码，details恰好一个 reservation.v1.PublicError(code=公开码)。映射分别为 Unauthenticated、PermissionDenied、InvalidArgument、NotFound、AlreadyExists(operation_conflict)、FailedPrecondition(out_of_stock)、Canceled、DeadlineExceeded、Unavailable(outcome_unknown)、Internal。失败 detail 不含底层错误。客户端先行超时/取消可能由gRPC本地生成状态：本实验精确检查 DeadlineExceeded/"context deadline exceeded" 或 Canceled/"context canceled"，details为空；不能要求已经断开的响应送达服务端detail。List 输入 limit 1..32；按 operation_id ASCII升序返回本主体快照，含 confirmed/rejected，有限条数、不分页、不持续订阅。服务端为应用查询派生2秒预算，客户端更早deadline保留；List的派生context覆盖查询及发送前检查，但已阻塞的stream.Send仍受原RPC context或Stop控制，不能称为独立的端到端2秒硬上限。流只有一个发送循环，无无界生产goroutine；Send错误立即返回。loopback TCP 明文只证明本实验的传输合同。

## 持久化不变量

- products.stock 永不为负。条件 UPDATE 同时完成数量判断与扣减，检查 RowsAffected 恰好为1或0
- operations 主键为(subject,operation_id)，输入列用ASCII二进制排序，避免大小写/排序规则偷偷合并身份
- 操作 claim、商品存在性检查、扣减和最终状态在同一个 READ COMMITTED 事务；pending只在未提交事务内可见
- 重复 claim 唯一键冲突后回滚本事务，用新的查询读取已提交结果；同键不同参数冲突
- 库存不足保存 rejected，未知商品回滚。后续补货不会改变旧操作结果
- 提交错误统一保守映射 outcome_unknown；用原主体和operation_id查询，不能新建操作ID盲重试
- 两仓储共享领域合同和显式迁移，GORM使用相同条件UPDATE和唯一约束；禁止AutoMigrate替代迁移
- 验收使用独立观察连接读取stock和operations；检查连接池InUse归零。禁止用SQLite、fake driver或内存结果冒充MySQL

## 架构和资源

HTTP/Gin与gRPC各自解读协议→同一个domain.Service→Repository接口→SQLStore/GORMStore→真实MySQL。公开DTO与数据库行类型分离。本例没有删除商品的入口，故operations.sku未加外键；若同时保留claim先行顺序与外键，两个事务可能各持商品共享外键锁再升级写锁，形成死锁。增加商品删除/API或外键时必须重审锁顺序与整笔事务重试，不能照搬本例。回调Hooks仅为测试可控交错/错误注入，默认进程永不配置故障；日志只写公开错误码。

HTTP与gRPC监听由同一进程拥有；健康/live 仅表示进程活着，/ready 在开始关闭后为503并检查短预算Ping。SIGTERM先撤ready、停止接纳，再在SHUTDOWN_GRACE窗口内等待已接纳调用（默认5秒，合法配置50ms..30s）；到期强制关闭并非零退出。Runtime显式等待两个Serve循环及HTTP/gRPC关闭调用，池最后Close。HTTP Close不承诺全部活动handler已返回；P04通过实际子进程Wait证明该进程已经退出，不能以此宣称MySQL服务端线程同时消失。

验证边界：真实TCP HTTP/gRPC + MySQL语义；可控Send错误单独标为协议适配单元测试。ACK丢失测试仅切断一次COMMIT响应，独立观察已提交结果，不能推论所有网络分区。慢消费测试只检查有限快照、取消及自有工作有界，不声称测得HTTP/2窗口背压或生产吞吐。

P04保持外部商品行锁跨越SIGTERM、精确exit=1/stderr及客户端EOF；锁未释放时的MySQL thread/transaction/wait计数仅记录事实，不要求它必须存在或已消失。进程退出后才释放测试拥有的行锁，再在1秒观察context内要求已捕获的processlist/thread/transaction/wait/data-lock身份全部消失；独立会话在释放前后均检查stock=10、operations=0、已提交pending=0。释放锁不增加COMMIT，也不用KILL制造清理。socket关闭和池关闭不是同步终止数据库执行的保证。
