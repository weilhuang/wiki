---
title: Java 平台
description: 从对象身份、集合与并发，连接到字节码、内存和运行时行为。语言/API 约定与某版 JDK 的实现分开阅读。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# Java 平台

从对象身份、集合与并发，连接到字节码、内存和运行时行为。语言/API 约定与某版 JDK 的实现分开阅读。

## 进入前与领域边界

能阅读 Java 方法、引用和异常；具体机制页补足最小先修。

Spring 的装配和事务属于框架；数据库并发属于数据与存储。Java 同步并不自动覆盖这些边界。

## 核心关系与阅读顺序

一份 Java 程序至少有三层约定：对象和 API 定义可见行为；集合与并发实现维护内部状态；JVM 把这些状态放到线程、内存和机器执行上。先说明相等性，才能判断 Map 是否新增；先说明共享与顺序，才能讨论锁是否必要。

先选一个会用却解释不清的对象合同，再读关键数据结构或同步机制，最后走到运行时证据。JVM 参数和并发工具名不应代替这一条因果链。

常见误区：某个 JDK 的节点布局不是 API 永久保证；一次没有抛异常也不能证明线程安全。容量、吞吐和延迟必须放回输入与负载条件。

**综合任务**：给一段集合代码换成可变键、碰撞输入或并发访问，分别预测外部结果；说明哪些判断来自 API，哪些依赖固定实现。

## 从分类进入

### 类型与对象

用值、身份和可变性解释对象合同。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：对象相等性与 hashCode、泛型与擦除、不可变对象。

### 集合

先选操作和顺序合同，再研究数组、散列与有序结构怎样承担它。

[分类导读](/knowledge/java/collections/)

- [HashMap 的查找、冲突与扩容](/knowledge/java/collections/hashmap.html)：用 A、B、C、D 四个键追踪身份匹配、桶内结构和扩容，再解释可变键、树化与选型边界
- [沿 OpenJDK 21 源码追踪 HashMap 的状态变化](/knowledge/java/collections/hashmap-source.html)：从 put 入口读到 putVal、resize 和树桶分支，核对计数、低高位拆分及不同 API 的树化边界

后续范围：ArrayList、LinkedHashMap、TreeMap、集合视图。

### 异常与资源

异常传播与资源释放是两种责任，需要在同一控制流里解释。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：try-with-resources、suppressed exception、资源所有权。

### 并发基础

把原子性、可见性、顺序和等待分开，才有条件判断线程安全。

[分类导读](/knowledge/java/juc-foundations/)

- [JMM 与安全发布：什么先于什么](/knowledge/java/juc-foundations/jmm-safe-publication.html)：从 value=42 与 ready 标志推导可见性，区分 happens-before、安全发布、final 与复合动作的原子性

后续范围：线程中断、复杂对象不变式、跨线程协议的更多反例。

### 同步与并发容器

比较锁、CAS、队列和快照承担的协作合同。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：synchronized、volatile、AQS、ConcurrentHashMap。

### 执行与编排

任务的接纳、排队、运行和取消有不同资源成本。

[分类导读](/knowledge/java/juc-execution/)

- [线程池如何接纳任务：线程、队列与拒绝](/knowledge/java/juc-execution/executor-admission.html)：沿 JDK21 execute、FutureTask 与 shutdown 的真实分支解释任务接纳、异常归属和关闭后的责任

后续范围：更多拒绝策略与 ThreadFactory 失败、CompletableFuture、ForkJoin、虚拟线程。

### JVM 执行与内存

沿加载、执行与可达性解释运行时状态，不把参数名称当作调优方法。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：类加载、栈帧、JIT、对象布局、GC。

### JVM 诊断

从负载和现象提出假设，再选择线程、分配或内存证据。

[分类导读](/knowledge/java/jvm-diagnostics/)

- [从线程与 GC 证据区分慢请求](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)：用真实平台线程快照、CPU 时间增量与 GC 日志，区分计算、monitor 阻塞、条件等待和分配压力

后续范围：JFR、GC 日志、OOM、堆外内存。

## 如何与其他领域连接

[安全发布](/knowledge/java/juc-foundations/jmm-safe-publication.html)与[任务接纳](/knowledge/java/juc-execution/executor-admission.html)解释本进程交接状态与工作；[线程证据](/knowledge/java/jvm-diagnostics/thread-gc-diagnosis.html)再帮助定位执行与等待。进入[Spring 容器](/knowledge/frameworks/spring-container/)时，继续追踪谁创建和持有这些对象。需要解释资源等待，转到[连接预算](/knowledge/frameworks/data-access/connection-budget.html)，不能用集合线程安全代替外部资源合同。
