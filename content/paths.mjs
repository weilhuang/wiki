export const paths = [
  { id:'spring-service-principles', title:'Spring 服务原理', source:'paths/spring-service-principles.md', status:'published',
    entry:['Java 调用与异常','HTTP 请求响应','SQL 提交与回滚'], goal:'解释对象、请求、事务和连接各自的完成边界，再评审一个本地订单接口。',
    stages:[
      {title:'对象与请求的责任', transition:'先确认协作者可用以及请求能否进入业务，后面的事务判断才有明确起点。', task:'画出协作者所有权和请求处理链；能解释业务尚未进入时为何返回错误。',readings:[
        {topic:'frameworks.bean-definition-registration',role:'optional',purpose:'需要追踪配置入口时，先看定义如何定位、解析和注册'},
        {topic:'frameworks.bean-lifecycle',role:'required',purpose:'区分定义、实例与内部资源的生命周期'},
        {topic:'frameworks.mvc-pipeline',role:'required',purpose:'定位参数解析、异常处理和响应提交'}]},
      {title:'数据与资源的边界', transition:'业务已经进入仍不等于数据已提交；请求慢也可能来自持有连接等待，需再加入事务与资源视角。', task:'预测事务最终结果与连接归还时机，比较短事务与跨外部等待的长事务。',readings:[
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
        {topic:'go.context-cancellation',role:'required',purpose:'区分取消信号、工作退出和业务提交'}]},
      {title:'限制工作与等待',transition:'取消只发信号，仍需明确谁等待任务、限制队列，以及谁关闭下游响应。',task:'给活动任务、队列和下游调用设可解释的边界。',readings:[
        {topic:'go.bounded-work',role:'required',purpose:'说明谁接纳、谁 join、谁关闭'},
        {topic:'go.client-budgets',role:'required',purpose:'让 Body、连接复用和重试共享总预算'}]},
      {title:'关闭进程前兑现责任',transition:'单次请求正确收尾不意味着整个进程可以退出，后台工作和共享依赖还有自己的责任。',task:'演练正常排空与强制退出，说明什么结果需要外部持久化。',readings:[
        {topic:'go.graceful-shutdown',role:'required',purpose:'按依赖顺序停止接纳、等待和释放资源'}]}
    ] },
  { id:'data-message-consistency', title:'数据与消息一致性', source:'paths/data-message-consistency.md', status:'published',
    entry:['SQL 与唯一约束','事务提交和回滚','两个会话的交错执行'], goal:'从业务不变量走到未知结果、事件交接、缓存和联合恢复，解释每个局部承诺。',
    stages:[
      {title:'先定义一次业务的事实',transition:'先解释一次写入怎样保持业务守恒，再让重试复用同一份裁决。',task:'写出守恒、唯一和终态合同，给超时后的查询保留稳定身份。',readings:[
        {topic:'data.inventory-invariants',role:'required',purpose:'用业务结果比较条件更新与锁定读取'},
        {topic:'distributed.idempotency',role:'required',purpose:'让重复参与同一裁决而非再次执行业务'}]},
      {title:'再推进跨组件责任',transition:'本地提交不能把事实自动送到消费者或缓存，必须增加持久交接与新鲜度合同。',task:'画出交接重投与旧值回填的窗口，比较方案增加的状态。',readings:[
        {topic:'distributed.transactional-outbox',role:'required',purpose:'区分事实提交、交付和消费提交'},
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
]
export const plannedPaths = [
  {id:'performance',title:'性能诊断',goal:'用负载和证据区分排队、连接、SQL 与运行时瓶颈',missing:'观测模型、SQL 和 profile 专题仍待补齐'},
  {id:'architecture-evolution',title:'系统设计与演进',goal:'从约束比较结构，再安排可逆迁移',missing:'先提供完整案例；通用建模和迁移专题继续补充'}
]
