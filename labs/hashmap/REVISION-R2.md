# R2 修订说明

R1 ZIP SHA256：`8e2d5200ebda3372459d4de159f9d5b222d1e518007bc5e3bd0b32d983c14d72`。R1 在原交付目录完整冻结，未覆盖；本公开包保留 R2 运行证据与揭示 R1 假通过的独立失败日志；较早的 R1 作者运行副本不重复分发。

## 独立审阅发现

1. R1 验证器只检查异常输出里包含目标文本和退出码 1。把断言改成带相同消息的 IllegalStateException，整体 verify 错误地通过
2. R1 computeIfAbsent 树化场景只检查 Entry 类型，未检查返回值、size 和全部 value。把回调结果从 8 改成 800，整体 verify 仍通过，与“逐键检查映射”的证据声明不符

这两点属于验证契约缺陷。没有据此改写 Java 机制来迁就测试，也没有仅仅缩小文字承诺。

## 代码修复

- 只接受异常首行为 java.lang.AssertionError、对应本轮目标命题且退出 1。错误异常类型、错误命题、预期失败意外成功均被拒绝
- computeIfAbsent 增加独立预期返回值 8、size=8、全部 8 项映射值断言；同时校验调用前 7 项 Node 状态及值
- 普通 put、默认增长、树拆分场景补充新增 put 的 null 返回、确定输入数量对应的 size、迁移前后逐项值与节点类型观察
- 新增可见的 check-regressions.py，隔离运行 reviewer 原有的 wrong-exception、compute-wrong-value、bad-positive，以及错误命题、预期失败意外成功、compute 丢旧映射、compute 污染旧值四个变异

## 文案与制品变化

- 两篇正文的机制、源码片段、API版本与图均未变
- 只补强验证附录中的异常识别方式、compute 映射断言范围和验证器回归说明
- README 增加缺陷与修复来由、可选回归运行方法；verification/delivery/source哈希按 R2 重建
- 官方源码、许可、主文可运行调用示例均保持字节不变
- R2 的新执行证据独立放在 run-r2-20261002 与 r2-regressions，R1 证据明确放历史目录，不能替代 R2 实际执行
