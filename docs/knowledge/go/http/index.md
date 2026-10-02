---
title: HTTP 服务与客户端
description: 输入、响应、Body、连接和预算共同构成调用合同。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# HTTP 服务与客户端

[知识目录](/knowledge/) / [Go 工程](/knowledge/go/)

输入、响应、Body、连接和预算共同构成调用合同。

## 阅读定位

Go error、接口、defer，以及 HTTP 的 header/body 与状态。

服务端先决定输入能否进入业务，再提交响应；客户端拥有每次响应 Body，并使用可共享的 Transport 管理连接。协议字节、函数返回和业务结果是三层观察。

## 怎样选择阅读入口

写服务从输入与响应合同进入；调用下游从客户端预算与 Body 责任进入。需要解释取消传播时回到并发协作。

常见混淆：一次 JSON Decode 成功不保证输入只有一个值；写响应无错误不等于客户端完整收到；关闭 Body 不保证所有条件下复用连接。

**小目标**：为相同接口分别设计非法输入、截断响应和超时测试，说明每条断言保护哪项合同。

## 可读主题

- [下游 HTTP 调用：连接复用、超时预算与有限重试](/knowledge/go/http/client-budgets.html)：用回环服务和可控时钟观察 Response.Body、连接复用、分阶段超时、重试放大与写入结果未知。
- [HTTP 管线与响应合同：谁解析、谁调用、谁写回](/knowledge/go/http/request-response-contract.html)：从真实 HTTP 请求追踪校验、中间件、业务调用和响应提交，用可复跑的失败矩阵定位错误边界。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

database/sql、JSON、代理与流式响应。这些是后续主题，未完成前不会产生空链接。
