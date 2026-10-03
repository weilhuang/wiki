---
title: Spring Boot
description: 配置来源、条件装配和应用生命周期各自回答不同问题。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# Spring Boot

[知识目录](/knowledge/) / [框架与服务通信](/knowledge/frameworks/)

配置来源、条件装配和应用生命周期各自回答不同问题。

## 阅读定位

Java注解、工厂方法；区分BeanDefinition与实例。

imports提出候选，条件按阶段观察环境与当时的定义，排序影响可见范围，容器随后按依赖创建对象。

## 怎样选择阅读入口

先改变类路径、属性与用户Bean，沿条件报告找到被拒绝的层，再追候选、排序与定义注册源码。

常见混淆：最终有某个Bean不证明此前OnBean能看到它；定义处理先后不是构造先后。

**小目标**：给同一默认实现加用户替代，核对数量、身份、构造次数及条件原因。

## 可读主题

- [自动配置为何生效：条件、顺序与退让](/knowledge/frameworks/spring-boot/conditional-configuration.html)：沿 imports 候选、条件阶段和定义注册追踪默认 Bean，用类路径、属性和用户 Bean 的变化解释装配结果与条件报告。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

配置绑定、Actuator、完整启动生命周期、AOT。这些是后续主题，未完成前不会产生空链接。
