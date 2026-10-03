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
- [Go 请求取消：从 context 传播到提交结果](/knowledge/go/concurrency/context-cancellation.html)：沿请求、工作 goroutine 和数据提交三条线理解 context，配合可运行实验区分取消信号、函数返回与业务结果。
- [BeanDefinition 从哪里来：定位、解析、注册与实例化的边界](/knowledge/frameworks/spring-container/bean-definition-registration.html)：跟随一个 XML 输入跨过 Spring 6.2.19 的真实类型分派，观察定义表、别名表与实例缓存如何变化，再连接注解和 Boot 入口。
- [请求完成链：MVC 在哪里选择处理器、转换异常和提交响应](/knowledge/frameworks/spring-mvc/request-pipeline.html)：用真实回环 HTTP 请求追踪 Filter、DispatcherServlet、参数校验、异常解析与响应提交，分清 HTTP 结果和业务副作用。
- [Spring 事务调用链：从代理入口到数据库连接](/knowledge/frameworks/spring-transactions/proxy-call-chain.html)：用十个可运行场景追踪自调用、线程绑定连接、rollback-only 和事务传播，解释异常与最终数据为什么会不一致。

## 一次阅读要留下什么

1. 入口前后的输入与状态，而非整类代码截图
2. 接口、抽象模板、实际实现与回调的角色
3. 主链和关键条件；没有发生的分支单独说明
4. 固定 tag/commit 的来源，以及 API 保证与当前实现的区别
5. 一项改变输入后的预测；如果做了运行，另记环境和验证范围

[实验与验证](/resources/experiments.html)区分源码复核和运行记录。代码块中的“示意”不等于上游原文，静态读懂一条分支也不等于已经运行全部路径。
