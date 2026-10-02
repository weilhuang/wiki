# 结果契约 v1

当前证据：NOT_RUN（MySQL/Redis）；STATIC_ONLY 的语法报告不提升此状态。

| 章节 / case | 必须实际观测的结果 |
|---|---|
| D1.naive_lost_update | initial=1、available=0、reserved=2；错误实现被识别 |
| D1.conditional_update | 第一请求影响1行，第二请求在等待后影响0行；守恒 |
| D1.locking_read | FOR UPDATE 两个请求依次读到1/0；守恒 |
| D1.snapshot_vs_current | RR普通读1、并发提交后普通读仍1、锁定读0 |
| D1.deadlock_cycle | 观测等待边，恰有一个1213，不假设victim身份，保留InnoDB状态 |
| D2.concurrent_same_key | 唯一键阻塞后1062，1订单、stock=9、复用相同结果 |
| D2.payload_conflict | 相同key不同规范payload拒绝，无第二副作用 |
| D2.before_commit_disconnect | KILL后operations/orders=0、stock=10，再试成功 |
| D2.after_commit_response_lost | 丢弃结果后同键重试仍1订单 |
| D2.retention_boundary | 清理op后稳定业务身份阻止重复；新业务身份可再执行 |
| D2.saved_rejection | 库存补回后旧键仍返回原rejected |
| D3.business_commit_before_relay | 无relay时outbox保存；恢复后投影出现 |
| D3.publish_before_mark | 两次accept、一次effect |
| D3.consumer_before_commit | dedup/effect一起回滚；重放一次 |
| D3.consumer_after_commit | dedup/effect一起保留；重放跳过 |
| D3.split_commit_negative_control | dedup已存在但投影缺失，错误实现被识别 |
| D4.stale_refill | DB v2，缓存v1，错误回填被识别 |
| D4.version_watermark | 水位v2下晚到v1两次被拒绝 |
| D4.invalidation_delivery_loss | 丢失失效命令时缓存仍v1，补发后删除 |
| D4.expiry_and_watermark_loss | value过期但floor保留；主动删floor后旧回填重新获准 |
| D4.concurrent_fill_after_floor | 并发v1/v2分别0/1，最终v2 |
| D5.six_failure_recovery | 1订单、stock=2、2投递、1effect、五组对账全部无违例 |
| D5.schema_v2_backwards_compatible_snapshot | v2后收到v1不回退；重复v2跳过 |

共23个基础case（D1=5、D2=6、D3=5、D4=5、D5=2）。各章独立创建环境并reset；all串行运行。最终判定同时需要所有期望用例、完整trace、正确镜像身份、退出码和清理记录。

待补验证而非本次通过项：真实broker ack/offset/重分配、多relay租约、Redis故障切换、真实HTTP未知结果、DB进程掉电耐久性、负载容量、线上迁移、外部副作用。
