---
title: Spring AOP
description: 从代理入口和接收者身份理解拦截器链。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# Spring AOP

[知识目录](/knowledge/) / [框架与服务通信](/knowledge/frameworks/)

从代理入口和接收者身份理解拦截器链。

## 阅读定位

Java接口、继承、引用；本页补足代理与目标的区别。

代理入口取得目标并建立方法拦截器链；proceed推进的是链上的游标，自调用的接收者则已经是目标。

## 怎样选择阅读入口

先跟随P与T的身份，再对照JDK/CGLIB入口，最后改变final、自调用与短路。事务的连接责任继续到事务页。

常见混淆：切换CGLIB不会自动修复自调用；final是否受限必须结合代理策略和调用入口。

**小目标**：画出一次outer到inner的实际接收者，改变调用点后预测通知和业务的进入次数。

## 可读主题

- [AOP 的接收者是谁：JDK、CGLIB 与拦截器分派](/knowledge/frameworks/spring-aop/proxy-dispatch.html)：从容器返回的对象追到真实业务接收者，用两种代理、final、自调用和短路解释哪些调用经过拦截器。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

复杂切点、动态 TargetSource、AspectJ、异步上下文。这些是后续主题，未完成前不会产生空链接。
