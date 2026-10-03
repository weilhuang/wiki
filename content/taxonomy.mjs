// Editorial groups are labels only; domain → category → topic is the public hierarchy.
export const taxonomy = [
  { id:'java', title:'Java 平台', summary:'从对象身份、集合与并发，连接到字节码、内存和运行时行为。语言/API 约定与某版 JDK 的实现分开阅读。', prerequisites:'能阅读 Java 方法、引用和异常；具体机制页补足最小先修。', boundary:'Spring 的装配和事务属于框架；数据库并发属于数据与存储。Java 同步并不自动覆盖这些边界。', categories:[
    ['objects','类型与对象','用值、身份和可变性解释对象合同。','对象相等性与 hashCode、泛型与擦除、不可变对象'],
    ['collections','集合','先选操作和顺序合同，再研究数组、散列与有序结构怎样承担它。','ArrayList、LinkedHashMap、TreeMap、集合视图'],
    ['resources','异常与资源','异常传播与资源释放是两种责任，需要在同一控制流里解释。','try-with-resources、suppressed exception、资源所有权'],
    ['juc-foundations','并发基础','把原子性、可见性、顺序和等待分开，才有条件判断线程安全。','线程中断、复杂对象不变式、跨线程协议的更多反例'],
    ['juc-synchronization','同步与并发容器','比较锁、CAS、队列和快照承担的协作合同。','synchronized、volatile、AQS、ConcurrentHashMap'],
    ['juc-execution','执行与编排','任务的接纳、排队、运行和取消有不同资源成本。','更多拒绝策略与 ThreadFactory 失败、CompletableFuture、ForkJoin、虚拟线程'],
    ['jvm-runtime','JVM 执行与内存','沿加载、执行与可达性解释运行时状态，不把参数名称当作调优方法。','类加载、栈帧、JIT、对象布局、GC'],
    ['jvm-diagnostics','JVM 诊断','从负载和现象提出假设，再选择线程、分配或内存证据。','JFR、GC 日志、OOM、堆外内存']
  ] },
  { id:'go', title:'Go 工程', summary:'围绕函数合同、并发所有权、标准库服务和进程生命周期组织 Go 知识。先解释谁启动、谁等待、谁关闭，再讨论工具选择。', prerequisites:'能阅读 Go 函数、接口、error 和 defer；并发页需要 channel/goroutine 的基本概念。', boundary:'context 是本进程协作协议，不是数据库提交结果或持久任务队列。跨服务恢复回到可靠交互。', categories:[
    ['language','语言核心','用具体值和控制流澄清语言约定。','值与指针、slice/map、接口 nil、error 链、泛型'],
    ['concurrency','并发协作与设计','把取消信号、工作退出和结果回收分开，再限制并发与队列。','sync、errgroup、背压、并发测试'],
    ['http','HTTP 服务与客户端','输入、响应、Body、连接和预算共同构成调用合同。','database/sql、JSON、代理与流式响应'],
    ['runtime','运行时','从可观察行为进入调度、netpoll、GC 和分配实现。','GMP、栈增长、内存模型、pprof/trace'],
    ['lifecycle','进程生命周期','先停止接纳，再等待已有工作，最后释放依赖。','就绪摘流、持久后台任务、容器终止窗口'],
    ['engineering','框架与工程','框架比较先说明它增加的状态和责任。','Gin、gRPC、配置日志、模块版本、测试替身']
  ] },
  { id:'frameworks', title:'框架与服务通信', summary:'沿请求进入、对象创建、代理调用和资源使用，解释应用框架与通信协议如何影响业务行为。', prerequisites:'基本函数调用、异常、HTTP 和 SQL；源码页明确固定版本与实际实现。', boundary:'框架定义调用与资源边界，不能替代数据库隔离、消息交付或业务幂等协议。', categories:[
    ['spring-container','Spring 容器','区分定义注册、实例创建、依赖注入、初始化和销毁。','IoC 基础、复杂定义与自定义命名空间、作用域扩展、循环依赖'],
    ['spring-aop','Spring AOP','从代理入口和接收者身份理解拦截器链。','复杂切点、动态 TargetSource、AspectJ、异步上下文'],
    ['spring-transactions','Spring 事务','把方法调用映射到连接上的事务，并跟踪正常与异常完成。','JDBC 本地事务、传播行为、同步回调、响应式边界'],
    ['spring-mvc','Servlet 与 MVC','沿处理器选择、参数、业务调用到响应提交解释请求链。','转换与校验、异常映射、异步请求、WebFlux'],
    ['data-access','数据访问与连接','连接占用、等待和事务范围共同决定服务资源成本。','JDBC、HikariCP、MyBatis、JPA、flush/N+1'],
    ['spring-boot','Spring Boot','配置来源、条件装配和应用生命周期各自回答不同问题。','配置绑定、Actuator、完整启动生命周期、AOT'],
    ['network','网络与 I/O','连接、传输与应用响应是不同层次的观察。','DNS、TCP、TLS、epoll、Reactor、连接复用'],
    ['api-rpc','HTTP API 与 RPC','建立错误、超时、重试和版本兼容的通信合同。','HTTP/2/3、gRPC、Netty、IDL、deadline、流控']
  ] },
  { id:'data', title:'数据与存储', summary:'先识别业务事实及不变量，再研究索引、事务、复制和派生数据如何保存或读取它。', prerequisites:'基本 SQL、唯一约束、提交与回滚；并发例子需要区分两个会话的执行顺序。', boundary:'缓存与搜索是派生视图；单数据库事务不会自动覆盖独立消息接收、外部支付或另一份投影。', categories:[
    ['modeling','关系建模','业务身份和约束决定数据库能够裁决什么。','主键与业务键、范式、Schema 演进'],
    ['indexes','索引与查询','从访问路径解释筛选、排序、回表和分页代价。','B+Tree、联合索引、执行计划、统计信息'],
    ['transactions','事务与并发业务','以不变量和会话交错判断事务、快照和锁的边界。','MVCC、Read View、undo/redo、记录锁与间隙锁'],
    ['availability','复制与恢复','明确读到什么、丢失多少和恢复到哪一刻。','复制延迟、GTID、备份、RPO/RTO、在线变更'],
    ['cache','缓存模型与一致性','区分命中收益、源数据年龄、失效窗口和回源成本。','Cache Aside、穿透与击穿、多级缓存、重建'],
    ['redis','Redis 机制与可用性','命令原子性、持久化与复制分别影响不同故障。','数据类型、Lua、过期淘汰、AOF、Sentinel、Cluster'],
    ['search-projections','搜索与读模型','派生视图需要定义刷新、推进和重新生成的责任。','倒排索引、Elasticsearch、CQRS、回放重建'],
    ['data-engineering','数据工程与流批','把指标口径、质量和同步责任连接到数据产出。','CDC、流批取舍、事件时间、水位、回填、血缘']
  ] },
  { id:'distributed', title:'消息与分布式', summary:'多个参与者无法共享同一次观察时，要分别说明身份、确认、顺序、重试和恢复。', prerequisites:'本地事务与请求响应；每篇另列需要理解的失败模型。', boundary:'一个受控协议替身能解释交错，不能代替真实 broker 的确认、复制、重平衡或网络分区验证。', categories:[
    ['reliable-interactions','可靠交互','未知结果需要稳定身份和查询入口，重试需要预算与责任。','退避、抖动、熔断、隔离舱、限流'],
    ['events','事件架构','保存已发生的事实及尚欠的交接，分清交付与消费提交。','Outbox 的真实 broker 实现、CDC、事件 Schema、事件溯源'],
    ['messaging','消息投递与产品机制','先定义确认含义，再比较队列、日志与消费模型。','Kafka、RocketMQ、RabbitMQ、顺序、重试死信'],
    ['recovery','消息恢复与运维','积压、去重、保留期与投影需要共同恢复。','毒消息隔离、有限重放、迁移消费者'],
    ['coordination','协调与共识','把故障模型、时钟假设和所有权有效期写清。','Raft、quorum、租约、fencing、分布式锁'],
    ['collaboration','跨边界数据协作','不同方案改变原子边界，也增加新的中间状态。','Saga、补偿、TCC、2PC/XA、跨服务查询'],
    ['durable-work','任务与状态','任务需要认领、接管、结果和终止协议。','持久工作流、定时调度、断点恢复']
  ] },
  { id:'architecture', title:'系统架构与演进', summary:'从业务约束和变化成本出发选择结构。模式用于解释一个决定解决了什么、又引出了什么。', prerequisites:'能描述业务目标、失败影响和已有边界；不要求预先选择微服务或消息系统。', boundary:'局部机制正确不代表整体方案适用。规模、组织、数据迁移和运维责任需要单独论证。', categories:[
    ['boundaries','建模与边界','用责任、依赖方向和数据归属界定模块。','质量属性、限界上下文、聚合、事务边界'],
    ['patterns','代码设计模式','围绕变化维度比较抽象和较简单的实现。','策略、工厂、适配器、装饰器、状态'],
    ['application','应用架构','比较结构对测试、部署、数据和协作的影响。','分层、六边形、模块化单体、微服务、CQRS'],
    ['evolution','架构演进','先判断是否值得变化，再设计可观察、可停止的小步迁移。','Strangler Fig、防腐层、分支抽象、数据回填'],
    ['business-cases','业务场景','用跨机制案例检验边界选择和失败处理。','库存预留、支付回调、批处理、多租户'],
    ['review','评审与复盘','把约束、备选方案、证据和退出条件放在同一份决定中。','ADR、容量估算、成本、风险、可逆决策']
  ] },
  { id:'cloud', title:'云原生与可靠性', summary:'从进程和资源出发，把交付、观测、服务目标与恢复联系起来。平台工具不能消除应用自身的生命周期责任。', prerequisites:'了解进程、网络和服务调用；诊断先记录工作负载和时间范围。', boundary:'本机停机不证明 Kubernetes 摘流；一次功能用例不证明容量、SLO 或多节点恢复。', categories:[
    ['processes','Linux 与进程','用进程、描述符和资源限制理解运行现场。','信号、namespace/cgroup、页缓存、资源统计'],
    ['containers','容器与工作负载','区分镜像、运行用户、网络和状态卷的责任。','镜像分层、Docker、Pod、Deployment、存储'],
    ['lifecycle','生命周期与弹性','启动、就绪、接纳和退出共同决定变更窗口。','探针、摘流、PDB、HPA、requests/limits'],
    ['delivery','交付与平台','同一制品逐步提升环境，数据变更需要兼容窗口。','CI/CD、灰度、功能开关、回滚、平台治理'],
    ['observability','观测与服务目标','选择能回答问题的指标、日志和追踪，控制基数与隐私。','RED/USE、SLI/SLO、采样、告警'],
    ['performance','性能与故障定位','用等待、资源持有与负载区分相似症状。','排队、Little 定律、profile、连接耗尽'],
    ['recovery','恢复与复盘','恢复必须对账并定义停止条件，不能只看进程重新启动。','备份演练、RPO/RTO、灾备、故障注入']
  ] },
  { id:'security', title:'身份与安全', summary:'每次访问都要明确主体、资源、动作和信任边界，再选择认证、授权及凭据生命周期。', prerequisites:'HTTP 与服务边界；认证证明身份，授权决定某次动作，两者不可互换。', boundary:'认证与授权各有信任边界。可运行示例限于可信身份输入后的顺序决策模型，不能替代真实身份供应商、密码学验证或多节点撤销测试。', categories:[
    ['trust','信任与威胁','先识别资产和跨越的边界，再讨论机制。','威胁建模、最小权限、默认拒绝'],
    ['authentication','认证','身份建立、会话延续和撤销需要完整生命周期。','MFA、完整 OAuth/OIDC 登录流程、签名库与密钥轮换'],
    ['authorization','授权','权限判定需要资源、动作和上下文。','RBAC、ABAC、ReBAC、数据库授权执行、列表与导出边界'],
    ['tenancy','多租户与服务身份','租户边界与机器身份需要独立的测试矩阵。','工作负载身份、mTLS、跨服务委托、真实服务跨租户集成测试'],
    ['credentials','凭据与审计','短期凭据、轮换和吊销影响泄漏的后果。','Secret、密钥证书、敏感日志'],
    ['api-security','Web 与 API 安全','输入处理和网络调用同时受信任边界约束。','注入、XSS/CSRF、SSRF、上传、供应链']
  ] },
  { id:'foundations', title:'计算机基础与工程方法', summary:'数据结构、操作系统和测试方法为上层机制提供可推理的模型；构建与协作让结论能被复核。', prerequisites:'可以从具体问题进入；不把整套基础课作为所有文章的统一门槛。', boundary:'工具执行成功只是一项观察。业务结果、错误实现、运行环境和来源身份仍需分别检查。', categories:[
    ['data-structures','数据结构与算法','从操作与复杂度选择结构，避免仅记名称。','数组、链表、哈希、树堆、图、布隆过滤器'],
    ['operating-systems','操作系统','进程、虚拟内存和 I/O 提供运行机制的下层解释。','调度、页缓存、文件系统、系统调用'],
    ['testing','软件测试','一个好断言要区分正确实现与相似的错误实现。','真实服务契约测试、属性测试、系统级故障注入'],
    ['builds','构建与依赖','把源码、依赖和制品身份固定下来，才知道复跑了什么。','Maven/Gradle、Go modules、锁定、许可证'],
    ['change','变更与协作','用评审、兼容窗口和可逆步骤控制变化风险。','Git、重构、技术债、ADR'],
    ['explanation','技术表达与复习','用改变条件后的推理检查理解。','源码阅读、机制解释、方案评审、故障复盘']
  ] }
].map(domain=>({...domain,categories:domain.categories.map(([id,title,summary,planned])=>({id,title,summary,planned:planned.split('、')}))}))
export const kinds = { concept:'机制解释', source:'源码解析', pattern:'模式与权衡', scenario:'场景方案', troubleshooting:'排障手册', lab:'实验教程', review:'复习与推理' }
export const relationLabels = { requires:'理解先修', recommendedBefore:'建议先读本文再读', related:'关联问题', contrastsWith:'对照比较', causesProblem:'引出的问题', addressesConsequence:'处理的后果', alternativeTo:'可替代方案', implements:'实现的机制', conflictsWith:'约束冲突' }
