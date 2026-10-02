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
]
export const plannedPaths = [
  {id:'java-core',title:'Java 核心机制',goal:'从对象相等性、集合和并发走到运行时诊断',missing:'JMM、执行器与 JVM 诊断尚未形成完整路线'},
  {id:'performance',title:'性能诊断',goal:'用负载和证据区分排队、连接、SQL 与运行时瓶颈',missing:'观测模型、SQL 和 profile 专题仍待补齐'},
  {id:'architecture-evolution',title:'系统设计与演进',goal:'从约束比较结构，再安排可逆迁移',missing:'先提供完整案例；通用建模和迁移专题继续补充'},
  {id:'identity-tenancy',title:'身份与多租户',goal:'明确主体、资源、动作和跨租户边界',missing:'认证与授权核心正文尚未发布，不提供开始完整路线入口'}
]
