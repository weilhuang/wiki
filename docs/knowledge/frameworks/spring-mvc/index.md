---
title: Servlet 与 MVC
description: 沿处理器选择、参数、业务调用到响应提交解释请求链。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# Servlet 与 MVC

[知识目录](/knowledge/) / [框架与服务通信](/knowledge/frameworks/)

沿处理器选择、参数、业务调用到响应提交解释请求链。

## 阅读定位

HTTP 方法、状态码、JSON 与 Java 调用/异常。

Mapping 找处理器，Adapter 准备并调用处理器，参数解析决定业务能否进入，返回值处理和容器把结果变成响应字节。异常处理只在尚可改变响应的范围内有效。

## 怎样选择阅读入口

先跟一次同步普通请求，再分别改变输入、业务异常和响应提交时机。异步与响应式处理不套用同一条线程链。

常见混淆：拦截器执行不代表 Controller 已进入；同样的状态码可能来自不同失败阶段；本例直接写响应和普通 DTO 返回要分开。

**小目标**：给三条失败请求记录业务进入次数、数据结果和完整响应，说明哪个观察能区分原因。

## 可读主题

- [请求完成链：MVC 在哪里选择处理器、转换异常和提交响应](/knowledge/frameworks/spring-mvc/request-pipeline.html)：用真实回环 HTTP 请求追踪 Filter、DispatcherServlet、参数校验、异常解析与响应提交，分清 HTTP 结果和业务副作用。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

转换与校验、异常映射、异步请求、WebFlux。这些是后续主题，未完成前不会产生空链接。
