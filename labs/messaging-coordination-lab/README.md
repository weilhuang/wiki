# 消息确认与资源端 fencing：受控模型

这里是原创 Python 标准库教学协议模型。没有真实 broker、数据库、Redis、etcd、网络或共识实现，不可作为生产服务部署。

## 运行

已验证 CPython 3.12.14 / Linux。无需安装任何包。

```bash
python3 --version
python3 -B walk_delivery.py
python3 -B walk_fencing.py
python3 -B verify.py > results.json
```

verify.py 的 JSON 输出包含每次精确命令、退出码、外部可读状态和源码 SHA-256。入口运行 10 个有限正确场景与 14 个目标错误版本，并检查 6 个验证器误识别探针。每个子进程 timeout=10 秒，stdout 为一条 JSON，stderr 必须为空；全部子进程 wait/join 后输出汇总。不启动服务器和线程，不创建临时文件。

单个正确场景例如：

```bash
python3 -B scenario_runner.py --scenario fencing-takeover --variant correct
```

目标错误实现应以退出码 1 输出 status=rejected、error_type=Violation 和精确失败代码。例如：

```bash
python3 -B scenario_runner.py --scenario fencing-takeover --variant no-fence
```

不能把这个命令退出 1 当任意错误均已验证：verify.py 同时检查场景、变体、异常类别、精确代码和非空业务证据。未预期异常退出 2，JSON/启动失败直接让验证失败。

## 模型的边界

- Store.committed 是字符串形式的逻辑持久快照。transaction 复制、修改并在一个顺序步骤替换整个快照；restart 从已提交字节重建对象。它不访问磁盘，不证明 fsync、数据库隔离、真实进程崩溃或存储掉电恢复
- broker、consumer、parking 各有独立 Store。broker 不做生产端去重；take(serial) 手动安排投递顺序，不能代表任何真实产品的调度算法、生产幂等、offset 或重平衡
- consumer 的 inbox 与 projection/effects 同时提交。固定单租户输入和唯一 event_id 为教学前提；稳定 ASCII 身份与操作载荷已经规范化，未测试任意不可信输入或身份拼接的编码问题
- poison 场景的 A2 故意留为 ready：它是需要后续业务恢复的版本缺口。测试结束没有悬挂 delivery tag；待处理业务状态不等于进程资源泄漏
- Authority 使用逻辑 tick，不实现时钟漂移、续租网络或选举。issued 是可信发行历史，不是“当前有效租约”查询；旧 grant 保留在集合中，确保资源端 fence 真正被测试
- Resource 只提供 write 动作，输入 principal 已经过外部认证；grant 由可信发行历史核验，scope 包含租户/资源/生命周期。没有密码学、真实 IdP、签名传输或策略引擎
- watermark 按资源键保存；epoch 由可信离线恢复步骤安装。水位、业务值、操作结果与 effects 在同一个模型事务提交。所有写路径必须经过 Resource.write，这也是生产系统需要另行实现的条件
- 同 token 支持不同 operation；同 operation_id/同载荷重放返回原结果。新 token 重放相同 operation 也复用结果并推进水位；较旧 token 在去重查询前被拒绝
- fencing 不保证租约到期瞬间旧请求立即失效。before-new-fence 明确展示新持有者尚未触达资源时，旧请求可被接受
- issuer-reset 的前提是停止/隔离旧写入者、可信地切换资源 epoch，再启动新发行器。这个测试不证明现实系统已经满足停写隔离条件
- 每个场景独立进程。错误版本终止时内存由进程退出释放；不运行无限循环、压力测试或外部清理操作

## 文件与证据

protocol_model.py 是完整模型，scenarios.py 是状态走读和精确断言，scenario_runner.py 输出某个场景的结构化结果，verify.py 执行有限场景和错误归因，walk_*.py 与文章 Code Hike 的干净源码逐字一致。

source-manifest.json 绑定源码、README、运行版本与许可证；ZIP 不包含解释器、依赖、二进制、缓存或新运行产物。网站单独发布 messaging-coordination-results.json，绑定实际运行过的六个 Python 文件 SHA-256。源码 ZIP 的生成不代表又运行了一次模型。

## 官方阅读入口

产品机制以 RabbitMQ 4.1 文档、Kafka 4.0 文档/4.0.2 客户端源码和 etcd v3.6 文档/v3.6.0 客户端源码为准；本模型不能替代产品集成测试。

- https://www.rabbitmq.com/docs/4.1/confirms
- https://www.rabbitmq.com/docs/4.1/queues
- https://kafka.apache.org/40/configuration/producer-configs/
- https://kafka.apache.org/40/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html
- https://github.com/apache/kafka/blob/4.0.2/clients/src/main/java/org/apache/kafka/clients/producer/KafkaProducer.java
- https://github.com/etcd-io/etcd/blob/v3.6.0/client/v3/concurrency/mutex.go
- https://github.com/etcd-io/etcd/blob/v3.6.0/client/v3/concurrency/session.go

没有复制上游代码。原创代码使用随包 MIT 许可证；被链接的 Kafka/etcd 源码为上游 Apache-2.0。
