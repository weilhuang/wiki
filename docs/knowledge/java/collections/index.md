---
title: 集合
description: 先选操作和顺序合同，再研究数组、散列与有序结构怎样承担它。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 集合

[知识目录](/knowledge/) / [Java 平台](/knowledge/java/)

先选操作和顺序合同，再研究数组、散列与有序结构怎样承担它。

## 阅读定位

Java 引用、equals/hashCode 的基本含义；散列与位运算可在 HashMap 主文补足。

集合先提供操作合同，再选择保存元素的结构。List 关心位置，Set 关心成员，Map 关心键与值的映射；顺序、相等性和并发要求决定这些接口之后还需要什么约束。

## 怎样选择阅读入口

先从键身份和桶模型理解 HashMap，再按一个具体输入走 put/resize。只有需要理解分支细节时才进入源码深读；有序或并发需求应触发容器比较。

常见混淆：哈希相同不等于键相等；树化阈值不应脱离容量条件；普通 Map 也不是包含过期与淘汰的完整缓存。

**小目标**：给同一组操作增加“按插入顺序遍历”或“多个线程更新”的要求，解释选择为什么要变。

## 可读主题

- [HashMap 的查找、冲突与扩容](/knowledge/java/collections/hashmap.html)：用 A、B、C、D 四个键追踪身份匹配、桶内结构和扩容，再解释可变键、树化与选型边界
- [沿 OpenJDK 21 源码追踪 HashMap 的状态变化](/knowledge/java/collections/hashmap-source.html)：从 put 入口读到 putVal、resize 和树桶分支，核对计数、低高位拆分及不同 API 的树化边界

这里按问题查找，不把排列位置当作强先修。每篇的“理解先修”说明真正需要的知识及原因；路线只提供推荐的推进顺序。

## 继续展开的范围

ArrayList、LinkedHashMap、TreeMap、集合视图。这些是后续主题，未完成前不会产生空链接。
