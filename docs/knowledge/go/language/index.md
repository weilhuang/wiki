---
title: 语言核心
description: 从值复制与别名进入 slice/map，再用动态类型和接收者解释接口、nil 与 error 链。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 语言核心

[知识目录](/knowledge/) / [Go 工程](/knowledge/go/)

从值复制与别名进入 slice/map，再用动态类型和接收者解释接口、nil 与 error 链。

## 阅读定位

能读 Go 函数、变量、赋值和返回值；不要求先记住运行时布局。

赋值先复制值，但 slice 和 map 的值仍可引用共享存储；接口保存动态类型和动态值，错误链再表达调用方可以识别的失败身份。这三种关系需要分别画出来。

## 怎样选择阅读入口

从 append 是否改变旧别名进入值专题，再用 typed nil 和错误包装核对接口边界。读完预测结果后，运行同一套标准库例子并替换一处错误实现。

常见混淆：复制 slice 不是复制底层数组；浅拷贝不隔离嵌套可变值；带 nil 指针的 error 接口未必等于 nil，公开错误信息也不应直接透传内部原因。

**小目标**：给一个返回集合和 error 的函数写明谁能修改哪些值，并分别断言正常结果、错误身份和公开响应。

## 可读主题

- [接口与错误：方法集、nil 与可恢复合同](/knowledge/go/language/interfaces-errors.html)：从一次成功却返回非 nil error 的调用开始，把接收者、动态类型、错误身份与公开响应分开验证
- [值与容器：slice、map 和别名](/knowledge/go/language/values-aliasing.html)：先预测一次 append 和一次快照复制的结果，再沿可变对象的引用检查所有权、nil 形状与复用条件

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

泛型约束与类型推断、反射、更多序列化边界。这些是后续主题，未完成前不会产生空链接。
