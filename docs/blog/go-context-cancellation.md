---
title: Go context 取消以后，写入会怎样？
description: 把请求取消、函数返回和数据提交放到同一条时间线上，理解 WithTimeout 的作用范围，以及超时之后为什么不能盲目重试。
date: "2026-10-02"
category: Go
tags: [Go, HTTP, context, 事务, 幂等]
order: 2
---

# Go context 取消以后，写入会怎样？

一个创建订单的接口超时了。客户端收到错误，服务端日志里出现 `context deadline exceeded`，数据库里却已经有了订单。

这几件事可以同时发生。超时说明某个等待期限到了；订单有没有提交，要看写入操作走到了哪一步。排查之前，先把两个问题分开：调用方还等不等，数据已经变成了什么。

本文按 Go 1.27.1 的标准库接口展开，示例只用 `context`、`fmt` 和 `time`。先修是函数、`error`、`defer` 和 channel 的基本用法。数据库部分讨论的是 `database/sql` 的接口约定，不把内存演示当成真实数据库验证。

## cancel 发出了信号，工作什么时候停？

`WithTimeout` 返回一个子 context 和一个取消函数。期限到达后，子 context 会进入取消状态；下游通过 `ctx.Done()` 或 `ctx.Err()` 观察它，再决定退出。调用 `cancel()` 本身不会等待工作结束。[官方 API](https://pkg.go.dev/context@go1.27.1#CancelFunc)对此有明确约定。

所以，仅仅把 context 传进函数，并没有给那个函数装上强制停止开关。如果它一直计算、等待一个不支持取消的操作，或者根本不检查 context，调用仍可能继续。

下面这个完整程序刻意安排了“写入完成后，再发生取消”：

```go
package main

import (
	"context"
	"fmt"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	saved := 0

	create := func(ctx context.Context) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		saved++ // 用内存计数模拟已经完成的副作用
		cancel()
		return nil
	}

	err := create(ctx)
	fmt.Println(err, ctx.Err(), saved)
}
```

输出是：

```text
<nil> context canceled 1
```

`create` 返回成功，context 已取消，计数仍然是 1。这里没有并发，也没有靠 `Sleep` 碰运气。它只说明一件事：取消状态不会自动替业务恢复已经改掉的数据。

## 在 HTTP 入口保留取消链

处理 HTTP 请求时，业务 context 通常应从 `r.Context()` 派生。服务端会在客户端连接关闭、HTTP/2 请求被取消，或者 `ServeHTTP` 返回后取消请求 context；具体时机见 [Request.Context 文档](https://pkg.go.dev/net/http@go1.27.1#Request.Context)。

如果在处理器中改用 `context.Background()`，这段工作就丢掉了父请求的取消信号、deadline 和上下文值。偶尔确实需要脱离请求生命周期的任务，但那需要明确的任务归属、停止条件和结果记录，不能靠换一个 context 随手实现。

下面这个函数封装一个同步调用。HTTP 处理器传入 `r.Context()`，`create` 则代表真正的业务操作：

```go
func createWithin(
	parent context.Context,
	budget time.Duration,
	create func(context.Context) (string, error),
) (string, error) {
	ctx, cancel := context.WithTimeout(parent, budget)
	defer cancel()

	if err := ctx.Err(); err != nil {
		return "", err
	}
	id, err := create(ctx)
	if ctxErr := ctx.Err(); ctxErr != nil {
		return "", ctxErr
	}
	return id, err
}
```

这段代码采用“返回时已经取消，就按取消结果处理”的应用策略。前置检查避免启动已知无效的工作；后置检查处理下游返回时取消已经发生的情况；`defer cancel()` 让操作提前完成时也能释放子 context 相关资源。

注意它的限度：后置检查通过到写响应之间，仍可能再次发生取消。它也不会撤销 `create` 已经提交的订单。错误响应最多说明这次请求没有拿到可确认的成功结果，不能据此断言订单不存在。

## 数据库事务有自己的取消约定

这里值得单独看 `database/sql`：把 context 传给 `DB.BeginTx` 后，该 context 覆盖事务直到提交或回滚。对于仍在进行中的事务，context 取消会触发 `sql` 包回滚；相关 `Commit` 也可能返回错误。[BeginTx 文档](https://pkg.go.dev/database/sql#DB.BeginTx)描述了这个约定。

这依然有明确边界。已经成功提交的事务，不会因为随后发生的请求取消被撤销；事务之外的 HTTP 调用、消息发送，也不会随这笔数据库事务一起回滚。底层查询能否及时响应取消，还需要核对具体驱动及数据库行为。

因此，写接口至少要分别记录提交结果与响应结果。若客户端只知道超时，重试前就可能面临“上一笔是否成功”的不确定性。常见处理办法是给业务请求分配幂等键，用数据库唯一约束保证唯一性，并把请求状态与业务写入放进合适的事务中。再次收到同一个键时，返回已有结果或处理中状态；同键不同参数则应拒绝。只在内存里记一下，进程重启后便失去了这层约束。

## 再套一层 goroutine，能不能准时返回？

可以让调用方在 `select` 中等结果或等 `ctx.Done()`，但选中了取消分支，并不代表工作 goroutine 已经结束。它可能继续占连接、改数据，甚至在无人接收的 channel 上阻塞。

如果这个 goroutine 还持有 `ResponseWriter`，处理器返回后再写响应会违反 `net/http` 的使用约定。让请求及时返回、让后台工作真正停止，是两个需要分别验证的条件。增加 goroutine 前，先确认下游能不能响应取消，以及退出后还有谁负责它。

也别把 `http.Server.WriteTimeout` 当成业务终止开关。它约束的是响应写入的 I/O 时间，不会替任意业务函数实现取消。业务预算从哪里开始也应写清：若输入解码后才调用 `WithTimeout`，之前读取和解析请求体的时间就没有包含在这笔预算中。

## 测试里至少安排这三种时序

- 调用前父 context 已取消：下游不应被调用
- 下游正在等待时取消：用 channel 确认它已经进入，再取消，观察它是否返回
- 下游已经产生副作用，再取消并返回成功：分别检查接口结果与数据状态，别只断言一个错误码

这三种情况对应三个不同的问题。把时序安排明确，通常比断言“必须在几毫秒内返回”更稳定，也更容易发现取消链中断在哪里。

如果你熟悉 Java，可以对照 [Spring 事务失效，先画出调用链](/blog/spring-transaction-proxy)一起看：异常、取消和回滚分别发生在哪一层，最终都要落到可观察的数据结果上。

## 源码与延伸阅读

- [context API，Go 1.27.1](https://pkg.go.dev/context@go1.27.1)
- [net/http API，Go 1.27.1](https://pkg.go.dev/net/http@go1.27.1)
- [database/sql 实现，go1.27.1](https://github.com/golang/go/blob/go1.27.1/src/database/sql/sql.go)
- [context 实现，go1.27.1](https://github.com/golang/go/blob/go1.27.1/src/context/context.go)
