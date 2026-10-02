---
title: Spring 容器
description: 区分定义注册、实例创建、依赖注入、初始化和销毁。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# Spring 容器

[知识目录](/knowledge/) / [框架与服务通信](/knowledge/frameworks/)

区分定义注册、实例创建、依赖注入、初始化和销毁。

## 阅读定位

Java 构造器、接口、异常和对象引用；读 XML 主链时能区分元素与属性。

Resource 提供输入，BeanDefinition 保存创建元数据，注册表保存名称和定义，BeanFactory 产生实例，生命周期回调管理可用与关闭。它们不是同一个状态。

## 怎样选择阅读入口

想知道对象从何而来，先读定义注册源码；想知道何时能使用或谁负责关闭，进入生命周期。两篇在实例创建边界汇合。

常见混淆：定义已注册不代表构造器已经执行；singleton 是容器内定义的作用域，也不代表后续修改线程安全。

**小目标：**分别画定义表、别名表和实例缓存，再改变懒加载或依赖关系，预测哪个状态会变化。

## 可读主题

- [BeanDefinition 从哪里来：定位、解析、注册与实例化的边界](/knowledge/frameworks/spring-container/bean-definition-registration.html)：跟随一个 XML 输入跨过 Spring 6.2.19 的真实类型分派，观察定义表、别名表与实例缓存如何变化，再连接注解和 Boot 入口。
- [容器创建与对象所有权：Bean 何时可用，谁负责关闭](/knowledge/frameworks/spring-container/bean-lifecycle.html)：从 BeanDefinition 到初始化和销毁，用对象身份、事件顺序与失败清理实验划清 Spring 容器和业务代码的资源责任。

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

IoC 基础、复杂定义与自定义命名空间、作用域扩展、循环依赖。这些是后续主题，未完成前不会产生空链接。
