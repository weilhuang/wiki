---
title: Spring 事务失效，先画出调用链
description: 从自调用和 UnexpectedRollbackException 两个反例出发，分清代理边界、回滚规则与共享事务，再决定该改哪一层。
date: "2026-10-02"
category: Java
tags: [Spring, 事务, JDBC, 源码阅读]
order: 1
---

# Spring 事务失效，先画出调用链

方法上有 `@Transactional`，异常也抛了，刚写进去的记录却还在。遇到这种情况，先别急着补 `rollbackFor = Exception.class`。更值得问的是：这次调用到底有没有经过事务拦截器？

本文以 Spring Framework 6.2.19、JDK 21、JDBC 本地事务为背景，使用默认的代理模式与 `DataSourceTransactionManager`。示例省略 Bean 配置和注入代码，不讨论 AspectJ 编织、响应式事务或跨数据库事务。读之前，知道 Spring Bean、Java 异常和数据库提交/回滚就够了。

## 同一个方法，换个入口就不回滚了

假设下面两个方法在同一个 Spring Bean 中，`jdbc` 是容器注入的 `JdbcTemplate`，`events` 是普通事务表：

```java
public void record() {
    recordAndFail();
}

@Transactional
public void recordAndFail() {
    jdbc.update("insert into events(label) values (?)", "created");
    throw new IllegalStateException("写入后失败");
}
```

从容器取出这个 Bean，直接调用 `recordAndFail()`，和调用 `record()`，走的并不是同一条路径：

```text
外部调用 recordAndFail
  → Spring 代理 → 事务拦截器 → 目标方法 → 异常 → 回滚

外部调用 record
  → Spring 代理 → record
                   → this.recordAndFail → 异常
                     ↑ 没有再次经过代理
```

第二条路径里，`record()` 没有事务配置，内部调用又绕过了代理。若调用前没有事务、连接使用自动提交，插入完成后便已提交，后面的异常无从撤销它。

这里有个容易漏掉的条件：**调用前没有事务**。如果外层已经开启事务，内部方法仍可能运行在那个事务里；只是内部方法自己的注解没有重新生效。于是，自调用上的 `REQUIRES_NEW` 也不会凭空创建独立事务。换成 CGLIB 类代理，同样不能修复这条自调用路径。[Spring 的代理模式说明](https://docs.spring.io/spring-framework/reference/6.2/data-access/transaction/declarative/annotations.html)明确区分了外部代理调用和对象内部调用。

## 修复前，先决定哪些操作必须一起成败

如果整个 `record()` 就是一笔业务，可以把事务放到这个对外入口。若同一个类既负责编排，又承担需要独立边界的写入，把写入拆成另一个 Bean 通常更清楚：编排服务调用容器注入的写入服务，调用自然经过后者的代理。

不想为了一个短边界拆类，也可以用 `TransactionTemplate`：

```java
public void record() {
    tx.executeWithoutResult(status -> {
        jdbc.update("insert into events(label) values (?)", "created");
        throw new IllegalStateException("写入后失败");
    });
}
```

这里的 `tx` 由管理同一数据源的事务管理器构造。事务边界就在回调中，不依赖另一个方法的注解。不过它默认仍是 `REQUIRED`，并不自动变成独立事务。两种写法的取舍主要在边界是否清楚，没必要为了“用注解”把调用关系绕复杂。

## catch 住异常，为什么最后还是提交失败？

另一种现象恰好相反：事务确实生效了，外层方法也正常执行完了，调用方却收到 `UnexpectedRollbackException`。

考虑两个不同的 Bean：外层方法与内层方法都采用默认的 `REQUIRED`。内层写入后抛出运行时异常，外层捕获它，继续做事。默认配置下，过程是这样的：

```text
外层代理：开启物理事务 T
  → 外层方法
     → 内层代理：加入 T
        → 内层方法抛出运行时异常
     ← 内层代理：将 T 标记为 rollback-only
     → 外层 catch，继续执行
  ← 外层方法正常返回
外层代理：尝试提交 T，发现只能回滚，抛出 UnexpectedRollbackException
```

`catch` 改变了 Java 控制流，却不会清掉事务状态。外层方法走到末尾，也不代表数据库已经提交。这个异常是在提醒调用方：原本期待的提交没有发生。[事务传播文档](https://docs.spring.io/spring-framework/reference/6.2/data-access/transaction/declarative/tx-propagation.html)用逻辑事务和物理事务解释了这一区别。

但不要反过来记成“只要 catch 就会报这个错”。如果异常在目标方法内部就被捕获，根本没有穿过事务拦截器，而且没有其他机制标记回滚，拦截器可能只看到一次正常返回。判断时必须标出异常在哪里抛出，又在哪里被接住。

## REQUIRES_NEW 会改变业务结果

把内层改成 `REQUIRES_NEW`，可以让它使用独立物理事务。比如要保留一条“订单处理失败”的审计记录，即使订单事务回滚，这条记录仍有独立提交的机会。

代价也很具体：审计和订单不再共同成败。若要求“订单成功才有这条记录”，这样的修改就改变了业务含义。外层持有数据库连接时，内层还可能申请另一条连接；高并发下需要一起检查连接池容量、嵌套层数和锁等待，不能只看异常消失了没有。

## 排查时，按这个顺序找证据

1. **确认入口。** 对象来自容器，还是自己 `new` 的？调用的是代理，还是同一个对象里的另一个方法？
2. **确认资源。** SQL 是否使用对应事务管理器管理的数据源？有没有绕过 Spring 自己创建连接？
3. **确认异常路径。** 哪个异常穿过了哪个代理边界？是否被捕获或转换？默认规则对运行时异常和 `Error` 回滚，受检异常另看配置。Spring 6.2 还支持全局修改默认回滚规则，不能只看方法上的注解。
4. **确认最终数据。** 在调用结束后检查数据库，分别覆盖“直接调用”和“内部调用”。用于验证边界的测试先不要额外套一层测试事务，否则它可能替业务代码提供了本来缺失的事务。

读源码也可以沿着这条线走：`TransactionInterceptor.invoke` → `TransactionAspectSupport.invokeWithinTransaction` → 事务管理器的提交或回滚。先找负责建立边界的代码，再看异常处理分支，比从一大串注解属性开始更容易解释现象。

如果还在把“请求报错”和“数据回滚”视为同一件事，可以接着读 [Go context 取消以后，写入会怎样？](/blog/go-context-cancellation)。语言和实现不同，但都需要把调用结果与数据状态分开核对。

## 源码与延伸阅读

- [Spring 6.2：使用 @Transactional](https://docs.spring.io/spring-framework/reference/6.2/data-access/transaction/declarative/annotations.html)
- [Spring 6.2：事务传播](https://docs.spring.io/spring-framework/reference/6.2/data-access/transaction/declarative/tx-propagation.html)
- [TransactionInterceptor，v6.2.19](https://github.com/spring-projects/spring-framework/blob/v6.2.19/spring-tx/src/main/java/org/springframework/transaction/interceptor/TransactionInterceptor.java)
- [TransactionAspectSupport，v6.2.19](https://github.com/spring-projects/spring-framework/blob/v6.2.19/spring-tx/src/main/java/org/springframework/transaction/interceptor/TransactionAspectSupport.java)
