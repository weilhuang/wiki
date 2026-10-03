---
title: 后端开发知识库
description: 从领域目录查机制，沿学习路线建立联系，用源码和实验检验判断。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
<div id="后端工程知识站" class="legacy-anchor" aria-hidden="true"></div>

# 后端开发知识库

这里围绕一个问题组织内容：**行为为什么这样发生，条件变化后应当怎样判断。** 从领域目录找具体机制；需要连成一条主线时，再选择有目标的学习路线。

- [按领域查知识](/knowledge/)：从分类进入机制、源码、模式与比较
<div id="选择一条学习路径" class="legacy-anchor" aria-hidden="true"></div>

- [按目标选择路线](/paths/)：看阅读准备、阅读目的和阶段任务
<div id="带着具体问题查找" class="legacy-anchor" aria-hidden="true"></div>

- [从场景或故障进入](/cases/)：先界定问题，再回到相关机制

## 知识领域

- [Java 平台](/knowledge/java/)：从对象身份、集合与并发，连接到字节码、内存和运行时行为。语言/API 约定与某版 JDK 的实现分开阅读。
- [Go 工程](/knowledge/go/)：围绕函数合同、并发所有权、标准库服务和进程生命周期组织 Go 知识。先解释谁启动、谁等待、谁关闭，再讨论工具选择。
- [框架与服务通信](/knowledge/frameworks/)：沿请求进入、对象创建、代理调用和资源使用，解释应用框架与通信协议如何影响业务行为。
- [数据与存储](/knowledge/data/)：先识别业务事实及不变量，再研究索引、事务、复制和派生数据如何保存或读取它。
- [消息与分布式](/knowledge/distributed/)：多个参与者无法共享同一次观察时，要分别说明身份、确认、顺序、重试和恢复。
- [系统架构与演进](/knowledge/architecture/)：从业务约束和变化成本出发选择结构。模式用于解释一个决定解决了什么、又引出了什么。
- [云原生与可靠性](/knowledge/cloud/)：从进程和资源出发，把交付、观测、服务目标与恢复联系起来。平台工具不能消除应用自身的生命周期责任。
- [身份与安全](/knowledge/security/)：每次访问都要明确主体、资源、动作和信任边界，再选择认证、授权及凭据生命周期。
- [计算机基础与工程方法](/knowledge/foundations/)：数据结构、操作系统和测试方法为上层机制提供可推理的模型；构建与协作让结论能被复核。

## 怎样使用一篇文章

先读开篇问题和适用范围，再沿图与具体输入解释状态变化。源码页把接口合同与固定版本实现分开；模式页比较约束、代价和简单替代。实验详情放在可展开附录，运行通过只支持它明确覆盖的条件。

<div id="如何判断自己学会了" class="legacy-anchor" aria-hidden="true"></div>

想检验理解，可以在[复习与推理](/resources/review.html)改变一个条件再预测结果；需要查具体实现，进入[源码阅读](/resources/source-reading.html)。未写内容集中标为规划，不会生成空知识页。
