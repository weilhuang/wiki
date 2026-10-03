---
title: 身份与安全
description: 每次访问都要明确主体、资源、动作和信任边界，再选择认证、授权及凭据生命周期。
prev: false
next: false
lastUpdated: false
generated: true
search: false
---
# 身份与安全

每次访问都要明确主体、资源、动作和信任边界，再选择认证、授权及凭据生命周期。

## 进入前与领域边界

HTTP 与服务边界；认证证明身份，授权决定某次动作，两者不可互换。

认证与授权各有信任边界。可运行示例限于可信身份输入后的顺序决策模型，不能替代真实身份供应商、密码学验证或多节点撤销测试。

## 核心关系与阅读顺序

主体提出对资源执行动作的请求；认证帮助确定主体，授权结合资源和上下文裁决动作，执行点负责落实决定，审计保留可追溯观察。服务身份、用户身份与租户边界不能混为一项登录状态。

先从一次请求携带的凭据进入，比较会话与令牌怎样保留状态；再在订单对象上加入租户、动作和委托条件。当前两篇解释这些判断，完整登录流程、密钥轮换和跨服务审计需要各自的专题。

常见误区：验证 JWT 签名不代表允许访问任意对象；知道订单 ID 不代表拥有订单；把租户 ID 从参数直接带入查询也不自动形成隔离。

**综合任务**：给订单读取和修改列“主体、租户、对象、动作”矩阵，包含其他租户、已撤销身份和服务代理场景；说明应该在哪个边界拒绝以及哪些敏感值不能进日志。

## 从分类进入

### 信任与威胁

先识别资产和跨越的边界，再讨论机制。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：威胁建模、最小权限、默认拒绝。

### 认证

身份建立、会话延续和撤销需要完整生命周期。

[分类导读](/knowledge/security/authentication/)

- [身份从哪里可信：会话、令牌与撤销边界](/knowledge/security/authentication/authentication-boundaries.html)：沿一条订单请求追踪身份凭据如何变成可信主体，比较服务端会话、自包含令牌和撤销状态的可见范围

后续范围：MFA、完整 OAuth/OIDC 登录流程、签名库与密钥轮换。

### 授权

权限判定需要资源、动作和上下文。

[分类导读](/knowledge/security/authorization/)

- [授权到哪一个对象：租户、主体与动作](/knowledge/security/authorization/object-tenant-authorization.html)：用订单读取、备注修改和只读委托推导默认拒绝策略，检查越租户、对象归属变更及授权后写入之间的窗口

后续范围：RBAC、ABAC、ReBAC、数据库授权执行、列表与导出边界。

### 多租户与服务身份

租户边界与机器身份需要独立的测试矩阵。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：工作负载身份、mTLS、跨服务委托、真实服务跨租户集成测试。

### 凭据与审计

短期凭据、轮换和吊销影响泄漏的后果。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：Secret、密钥证书、敏感日志。

### Web 与 API 安全

输入处理和网络调用同时受信任边界约束。

本分类正文仍在规划，当前不提供空文章链接。

后续范围：注入、XSS/CSRF、SSRF、上传、供应链。

## 如何与其他领域连接

[会话与令牌](/knowledge/security/authentication/authentication-boundaries.html)确定哪些身份声明可以信任；[对象授权](/knowledge/security/authorization/object-tenant-authorization.html)再将主体与当前订单事实联系起来。提交前权限发生变化时，需要与[库存不变量](/knowledge/data/transactions/inventory-invariants.html)中的并发裁决一起思考。错误响应与日志还要遵守[HTTP 响应边界](/knowledge/go/http/request-response-contract.html)。
