export const paths = [
  { id:'spring-service-principles', title:'Spring 服务原理', source:'paths/spring-service-principles.md', status:'published',
    entry:['Java 调用与异常','HTTP 请求响应','SQL 提交与回滚'], goal:'解释对象、请求、事务和连接各自的完成边界，再评审一个本地订单接口。',
    stages:[
      {title:'对象与请求的责任', transition:'先确认协作者可用以及请求能否进入业务，后面的事务判断才有明确起点。', task:'画出协作者所有权和请求处理链；能解释业务尚未进入时为何返回错误。',readings:[
        {topic:'frameworks.bean-definition-registration',role:'optional',purpose:'需要追踪配置入口时，先看定义如何定位、解析和注册'},
        {topic:'frameworks.boot-conditions',role:'optional',purpose:'排查自动配置时，比较候选条件、定义顺序与用户 Bean 退让'},
        {topic:'frameworks.bean-lifecycle',role:'required',purpose:'区分定义、实例与内部资源的生命周期'},
        {topic:'frameworks.mvc-pipeline',role:'required',purpose:'定位参数解析、异常处理和响应提交'}]},
      {title:'数据与资源的边界', transition:'业务已经进入仍不等于数据已提交；请求慢也可能来自持有连接等待，需再加入事务与资源视角。', task:'预测事务最终结果与连接归还时机，比较短事务与跨外部等待的长事务。',readings:[
        {topic:'frameworks.aop-dispatch',role:'optional',purpose:'需要解释调用入口时，先比较代理、目标和自调用的接收者'},
        {topic:'frameworks.transaction-proxy',role:'required',purpose:'跟踪代理、回滚标记和线程绑定连接'},
        {topic:'frameworks.connection-budget',role:'required',purpose:'解释连接占用与排队，区分超时和终止'}]},
      {title:'把边界放进同一个服务',transition:'分别解释四层还不够，提交后响应失败等跨层窗口需要在同一接口中评审。',task:'提交有备选方案、失败矩阵和未覆盖项的设计评审。',readings:[
        {topic:'architecture.local-service-boundary',role:'required',purpose:'同时核对 HTTP、持久数据和资源结果'}]}
    ] },
  { id:'go-reliable-services', title:'Go 可靠服务', source:'paths/go-reliable-services.md', status:'published',
    entry:['Go 函数、error 与 defer','channel 与 goroutine','HTTP 请求响应'], goal:'为请求、工作、下游调用和进程退出定义所有者、等待上限与资源收尾。',
    stages:[
      {title:'先把请求合同写清',transition:'从公开输入和响应开始，先知道服务承诺什么，再讨论请求取消后的工作。',task:'用同一输入分别预测公开响应、业务进入和副作用。',readings:[
        {topic:'go.http-contract',role:'required',purpose:'建立入口拒绝顺序与完整响应合同'},
        {topic:'go.channel-memory-ownership',role:'optional',purpose:'需要解释交接规则时，先区分收发同步、对象别名和工作结束'},
        {topic:'go.context-cancellation',role:'required',purpose:'区分取消信号、工作退出和业务提交'}]},
      {title:'限制工作与等待',transition:'取消只发信号，仍需明确谁等待任务、限制队列，以及谁关闭下游响应。',task:'给活动任务、队列和下游调用设可解释的边界。',readings:[
        {topic:'go.bounded-work',role:'required',purpose:'说明谁接纳、谁 join、谁关闭'},
        {topic:'go.client-budgets',role:'required',purpose:'让 Body、连接复用和重试共享总预算'},
        {topic:'go.runtime-wait-diagnosis',role:'optional',purpose:'定位慢请求时，用实际栈、profile与trace区分执行、等待和输入堆积'}]},
      {title:'关闭进程前兑现责任',transition:'单次请求正确收尾不意味着整个进程可以退出，后台工作和共享依赖还有自己的责任。',task:'演练正常排空与强制退出，说明什么结果需要外部持久化。',readings:[
        {topic:'go.graceful-shutdown',role:'required',purpose:'按依赖顺序停止接纳、等待和释放资源'}]}
    ] },
  { id:'data-message-consistency', title:'数据与消息一致性', source:'paths/data-message-consistency.md', status:'published',
    entry:['SQL 与唯一约束','事务提交和回滚','两个会话的交错执行'], goal:'从业务不变量走到未知结果、事件交接、缓存和联合恢复，解释每个局部承诺。',
    stages:[
      {title:'先定义一次业务的事实',transition:'先解释一次写入怎样保持业务守恒，再让重试复用同一份裁决。',task:'写出守恒、唯一和终态合同，给超时后的查询保留稳定身份。',readings:[
        {topic:'data.inventory-invariants',role:'required',purpose:'用业务结果比较条件更新与锁定读取'},
        {topic:'data.mvcc-read-views',role:'optional',purpose:'需要解释读取差异时，区分普通视图、当前读取和自己的写入'},
        {topic:'data.index-access-paths',role:'optional',purpose:'把索引定位、过滤、取列和排序分开，并比较估计与实际计划'},
        {topic:'distributed.idempotency',role:'required',purpose:'让重复参与同一裁决而非再次执行业务'}]},
      {title:'再推进跨组件责任',transition:'本地提交不能把事实自动送到消费者或缓存，必须增加持久交接与新鲜度合同。',task:'画出交接重投与旧值回填的窗口，比较方案增加的状态。',readings:[
        {topic:'distributed.transactional-outbox',role:'required',purpose:'区分事实提交、交付和消费提交'},
        {topic:'distributed.delivery-ack-boundaries',role:'required',purpose:'追踪确认究竟覆盖保存、投递还是消费提交，处理重投与按键缺口'},
        {topic:'distributed.lease-fencing',role:'optional',purpose:'存在租约接管时，让接收端拒绝已被新代次取代的旧持有者'},
        {topic:'data.cache-invalidation',role:'required',purpose:'为不同读取定义新鲜度与恢复责任'}]},
      {title:'最后联合恢复和停止',transition:'每个组件各自恢复仍可能留下缺口，需要在同一数据集上联合对账并决定何时停止。',task:'恢复后检查守恒、投影和待交接责任，而非只检查服务存活。',readings:[
        {topic:'architecture.consistency-recovery',role:'required',purpose:'用权威事实对账、限定重放并验证兼容迁移'}]}
    ] }
  ,{ id:'identity-tenancy', title:'身份与多租户', source:'paths/identity-tenancy.md', status:'published',
    entry:['能区分 HTTP 请求的调用方与服务端','能读条件判断和一条订单记录'], goal:'从可信身份进入一次订单操作，比较撤销时效，并为租户、对象、动作与提交时刻建立默认拒绝规则。',
    stages:[
      {title:'先界定身份与撤销的责任',transition:'请求带来的声明要经过可信验证才可当作身份。在线状态、自包含令牌和缓存的成本不同，撤销生效时间也不同。',task:'画出同一凭据在在线检查、离线校验和旧缓存下的决策，说明各自依赖谁、何时能看到撤销。',readings:[
        {topic:'security.authentication-boundaries',role:'required',purpose:'区分身份建立、令牌验证、会话状态与撤销可见性'}]},
      {title:'把身份放回具体对象与时刻',transition:'已经知道调用者是谁，仍需核对他对当前租户和对象能做哪项动作；准备阶段的允许不能自动沿用到事实已经改变的提交阶段。',task:'列出本人、同租户他人、跨租户和受托方的读取/修改矩阵；再改变归属、成员资格和对象版本，预测提交结果。',readings:[
        {topic:'security.object-tenant-authorization',role:'required',purpose:'按主体、租户、对象、动作与当前版本逐项裁决'}]},
      {title:'用反例检查拒绝是否真的生效',transition:'正常用户能成功只证明一条路径。要把缺少动作限制、过期身份和旧准备重复提交等错误逐项变成可识别的失败。',task:'运行有限策略模型，核对允许或拒绝、精确副作用和版本；说明模型尚未覆盖的密码学、身份供应商与真实数据库执行。',readings:[
        {topic:'foundations.assertion-counterexamples',role:'optional',purpose:'需要编写验证器时，区分业务反例、启动错误和资源收尾'}]}
    ] }
  ,{ id:'java-core', title:'Java 核心机制', source:'paths/java-core.md', status:'published',
    entry:['能阅读 Java 引用、字段、方法与异常','知道线程可以共享对象；每篇补足具体同步概念'], goal:'从键与对象状态进入跨线程可见性，再跟踪任务接纳、结果所有权与运行时证据。',
    stages:[
      {title:'先说明保存的是什么状态',transition:'集合的相等性和结构回答状态怎样存放，跨线程使用还要加入发布边界；两者不能互相替代。',task:'说明一个可变键如何破坏查找，再画出把包含集合的对象交给另一线程时需要的发布关系。',readings:[
        {topic:'java.hashmap',role:'required',purpose:'从键身份、桶与扩容理解普通容器的约定'},
        {topic:'java.hashmap-source',role:'optional',purpose:'需要核对具体分支时追踪 put、resize 与不同树化入口'},
        {topic:'java.jmm-safe-publication',role:'required',purpose:'区分可见性、原子性、final 与安全发布'}]},
      {title:'再交接工作和结果',transition:'对象可见只解决输入的一部分问题，任务仍需要被接纳、执行、观察结果并在关闭时收尾。',task:'给四个受控任务画接纳分支，分别核对线程、队列、异常与 Future 的最终责任。',readings:[
        {topic:'java.executor-admission',role:'required',purpose:'沿真实 execute、FutureTask 与关闭分支解释任务所有权'}]},
      {title:'让证据区分相似的慢请求',transition:'理解任务在哪里排队和执行之后，才有条件把线程栈与 CPU、GC 的观察接回请求，而不是看到状态就下结论。',task:'比较两个线程快照和同一线程的 CPU 增量，列出仍缺失的业务、负载或时间窗口信息。',readings:[
        {topic:'java.jvm-diagnosis',role:'required',purpose:'区分计算、monitor 阻塞、条件等待与分配压力'},
        {topic:'foundations.blocking-waiting',role:'optional',purpose:'需要跨出 JVM 时，把等待条件继续追到连接或下游持有者'}]}
    ] }
  ,{"id": "service-reliability", "title": "服务观测与发布可靠性", "source": "paths/service-reliability.md", "status": "published", "entry": ["了解一次请求的输入、结果与超时", "能区分新工作接纳和已有工作完成；正文补充分布与探针概念"], "goal": "先定义用户事件与服务目标，再用局部证据定位原因，最后解释发布时的路由、排空和资源释放。", "stages": [{"title": "定义用户看到的结果", "transition": "服务目标需要明确事件边界和好事件条件，才能判断一组请求是否满足目标。", "task": "给固定订单样本计算好事件比例和预算；改变流量分配，说明哪些百分位算法会失效。", "readings": [{"topic": "cloud.service-level-signals", "role": "required", "purpose": "区分事件总体、采样、比例和分布，处理零流量与基数成本"}]}, {"title": "让证据区分相似症状", "transition": "目标未达标只说明用户结果，下一步要用相同窗口的证据寻找执行、等待或输入堆积。", "task": "为 CPU 低而请求变慢提出两个原因，选择能排除一个原因的下一项观察，并保留测量范围。", "readings": [{"topic": "foundations.blocking-waiting", "role": "optional", "purpose": "需要基础模型时，从线程与资源持有者区分计算和等待"}, {"topic": "go.runtime-wait-diagnosis", "role": "optional", "purpose": "Go 服务用有限真实进程练习栈、profile与trace之间的区别"}, {"topic": "java.jvm-diagnosis", "role": "optional", "purpose": "Java 服务对照线程 CPU 增量、锁和GC观察"}, {"topic": "cloud.connection-waiting", "role": "required", "purpose": "把入口症状接回连接等待与实际持有者"}]}, {"title": "把发布窗口放进同一时间线", "transition": "平台状态和应用状态分属不同所有者。目标与观察范围明确后，再安排摘流、停止接纳、等待及依赖释放。", "task": "安排一个端点已变但路由未刷新的请求，写出何时接纳或拒绝、旧工作何时结束，以及何时停止发布。", "readings": [{"topic": "go.graceful-shutdown", "role": "optional", "purpose": "需要应用侧实例时，观察正常排空、强制退出和依赖顺序"}, {"topic": "cloud.readiness-draining", "role": "required", "purpose": "区分探针、端点消费者与进程责任，并说明真实集群尚未验证的部分"}]}]}
  ,{"id": "architecture-evolution", "source": "paths/architecture-evolution.md", "status": "published", "title": "系统设计与演进", "entry": ["能描述业务不变量与本地事务", "每篇补足最小背景，跨域主题按问题选读"], "goal": "提交可反驳、可停止且写清失败与恢复责任的架构决定。", "stages": [{"title": "划出变化与事实边界", "transition": "先分清依赖、数据、提交与部署，再问哪种接缝能挡住无关牵连。", "task": "比较四种结构的变化代价与测试切面。", "readings": [{"topic": "architecture.module-boundaries", "role": "required", "purpose": "建立四种边界与数据所有权"}]}, {"title": "保留最简单的充分方案", "transition": "有了边界，再核对独立运行的收益是否足以承担迁移成本。", "task": "从约束比较不拆、局部隔离和独立服务。", "readings": [{"topic": "architecture.order-service-extraction", "role": "required", "purpose": "沿用已发布迁移案例，不复制正文"}]}, {"title": "评审到能够停止", "transition": "选择结构后仍要让权限、目标、预算和恢复在同一变更上成立。", "task": "交付取消流程的权限表、预算、失败矩阵和回退决定。", "readings": [{"topic": "architecture.order-reliability-review", "role": "required", "purpose": "完成一份可被反例推翻的评审样板"}]}]}
]
export const plannedPaths = [
  {id:'performance',title:'性能诊断',goal:'用负载和证据区分排队、连接、SQL 与运行时瓶颈',missing:'已有服务目标与 Java/Go 有限诊断；代表性负载、容量模型和端到端性能实验仍待补齐'}
]
