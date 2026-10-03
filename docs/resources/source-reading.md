---
title: 源码阅读
description: 以输入、接收者、调用链和状态变化组织源码阅读。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 源码阅读

先写出想解释的外部行为，再固定版本、入口和输入。跟踪当前接收者是谁、为何分派到该实现、哪个分支修改了哪项状态；最后回到可见结果。

## 已有源码主线

- [HashMap 的查找、冲突与扩容](/knowledge/java/collections/hashmap.html)：用 A、B、C、D 四个键追踪身份匹配、桶内结构和扩容，再解释可变键、树化与选型边界
- [沿 OpenJDK 21 源码追踪 HashMap 的状态变化](/knowledge/java/collections/hashmap-source.html)：从 put 入口读到 putVal、resize 和树桶分支，核对计数、低高位拆分及不同 API 的树化边界
- [线程池如何接纳任务：线程、队列与拒绝](/knowledge/java/juc-execution/executor-admission.html)：沿 JDK21 execute、FutureTask 与 shutdown 的真实分支解释任务接纳、异常归属和关闭后的责任
- [channel 的同步与关闭：谁交接、谁结束](/knowledge/go/concurrency/channel-memory-ownership.html)：从一个重复使用的字节切片推导收发、缓冲与关闭的内存边界，再区分对象交接、select 就绪和工作结束
- [Go 请求取消：从 context 传播到提交结果](/knowledge/go/concurrency/context-cancellation.html)：沿请求、工作 goroutine 和数据提交三条线理解 context，配合可运行实验区分取消信号、函数返回与业务结果。
- [goroutine 为什么在等：调度、netpoll 与诊断证据](/knowledge/go/runtime/scheduler-netpoll-diagnosis.html)：沿四个有界真实进程区分计算、channel 阻塞、TCP 网络等待和工作堆积，用栈、CPU profile 与 trace 逐步缩小判断范围
- [AOP 的接收者是谁：JDK、CGLIB 与拦截器分派](/knowledge/frameworks/spring-aop/proxy-dispatch.html)：从容器返回的对象追到真实业务接收者，用两种代理、final、自调用和短路解释哪些调用经过拦截器。
- [自动配置为何生效：条件、顺序与退让](/knowledge/frameworks/spring-boot/conditional-configuration.html)：沿 imports 候选、条件阶段和定义注册追踪默认 Bean，用类路径、属性和用户 Bean 的变化解释装配结果与条件报告。
- [BeanDefinition 从哪里来：定位、解析、注册与实例化的边界](/knowledge/frameworks/spring-container/bean-definition-registration.html)：跟随一个 XML 输入跨过 Spring 6.2.19 的真实类型分派，观察定义表、别名表与实例缓存如何变化，再连接注解和 Boot 入口。
- [请求完成链：MVC 在哪里选择处理器、转换异常和提交响应](/knowledge/frameworks/spring-mvc/request-pipeline.html)：用真实回环 HTTP 请求追踪 Filter、DispatcherServlet、参数校验、异常解析与响应提交，分清 HTTP 结果和业务副作用。
- [Spring 事务调用链：从代理入口到数据库连接](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)：用十个可运行场景追踪自调用、线程绑定连接、rollback-only 和事务传播，解释异常与最终数据为什么会不一致。
- [租约过期以后：旧持有者为什么仍需 fencing](/knowledge/distributed/coordination/lease-fencing.html)：用暂停后恢复的两个工作者解释租约与资源端栅栏，追踪单调 token、同租约多操作、重放去重和水位恢复的边界

## 一次阅读要留下什么

1. 入口前后的输入与状态，而非整类代码截图
2. 接口、抽象模板、实际实现与回调的角色
3. 主链和关键条件；没有发生的分支单独说明
4. 固定 tag/commit 的来源，以及 API 保证与当前实现的区别
5. 一项改变输入后的预测；如果做了运行，另记环境和验证范围

[实验与验证](/resources/experiments.html)区分源码复核和运行记录。代码块中的“示意”不等于上游原文，静态读懂一条分支也不等于已经运行全部路径。
