# Java 服务机制实验

同一套有限实验连接三个问题：共享状态怎样发布、任务交给谁执行、慢在哪里。教学源码 MIT；OpenJDK 原文件保留 GPLv2 + Classpath exception 与版权头。

## 环境与复现

需要完整 JDK 21 和 Python 3 标准库，无第三方依赖，无网络、端口或容器。设置 JAVA_HOME 为本机 JDK 21 根目录，然后在本目录运行：

```sh
python3 run.py --output proof/local-run
python3 check_evidence.py
```

`run.py` 拒绝覆盖输出目录。编译放临时目录，退出清理；java 子进程最大堆64MiB、初始32MiB、ActiveProcessorCount=2、SerialGC。ActiveProcessorCount 是 JVM 可用处理器提示，不是操作系统硬配额；堆大小不含整个 JVM 的非堆内存。并发实验门闩/屏障等待最多3秒，Java子进程最多15秒、编译20秒；诊断进程有12秒 watchdog，异常路径还会终止其进程组。诊断有四个工作线程、一个daemon watchdog和主线程，JVM另有内部线程。总分配payload256MiB，最终数组payload保留2MiB；不是内存泄漏压力测试。

`check_evidence.py` 读取仓库中保存的 run-r4 证据，执行静态判断与 runner 异常归因回归，不启动 JVM，也不自动转向新的 local-run。要审阅新运行，应显式核对其 result.json、全部输出和对应源哈希。

## 文件

- src/PoolCleanup.java：放行后有界有序关闭，真实超时才强停并报告清理失败
- src/HarnessContracts.java：真实有限池验证清理顺序、主异常保留、Throwable身份去重与不同子异常保留
- src/ChildFailures.java：普通子线程错误收集、原始cause传播与线程join
- src/Publication.java：单次 volatile 发布的教学类
- src/JmmLab.java：有限发布运行、屏障控制丢更新与 AtomicInteger
- src/ExecutorLab.java：A/B/C/D 接纳、有序关闭、异常归属、shutdownNow 结果责任，以及 offer/关闭交错
- src/DiagnosticLab.java：同进程 ThreadMXBean 状态/栈/monitor 与CPU测量，有限环形分配
- sources/：固定 jdk-21+35 与运行工具链 src.zip 的三个完整类；sources/history/ 保存外部 jcmd 失败时的诊断源与 runner
- proof/run-r4/：实际成功运行，版本、正例、负例、线程/GC原始文本及源哈希
- proof/jcmd-attempt.json：首次外部 jcmd 超时的去路径摘要；不把失败标为成功
- proof/evidence-check.json：检查实际证据、普通正例/交互输出完整性与错误归因的静态结果
- proof/r3-regressions/：源码注入故障的完整被测源码、差异、失败输出、cause和清理证据
- package_public.py：源码、许可、元数据和指定文本证据的显式白名单，不打包attach/cache/binary残留
- source-review.json、snippets.json：固定源身份、审閱范围和逐段提取关系

## 实际记录与版本边界

运行时是 Temurin 21.0.12.1+1-LTS；讲解的固定源基线是 OpenJDK jdk-21+35。ThreadPoolExecutor、AbstractExecutorService、FutureTask 三个 GA 文件与此运行工具链 src.zip 中对应类恰好字节相同，不能推广为整个构建一致。所有Java正例exit0，三个目标反例exit1且首异常行严格匹配java.lang.AssertionError与完整目标消息。

R1 的 jcmd Thread.print 在 READY 后8秒超时，因此没有外部附加诊断成功证据。成功路径改用应用内标准 ThreadMXBean.dumpAllThreads(true,true)，输出实际状态、完整栈、锁owner与持有monitor；它需要插桩，不等价于能够附加任意未改动服务。没有执行JFR、虚拟线程、真实网络服务、生产容量测试或性能排名。

JMM正例实际读到42不构成所有执行的证明；volatile复合动作反例由屏障控制，删除volatile后的重排序不设为强制复现条件。CPU与GC数字只属于这一次运行。负例解析回归还拒绝相同消息的RuntimeException、错误线程、编译/启动失败与非预期成功退出。

## 子线程失败与完整结果

join只证明线程结束。普通JMM/诊断/执行器worker由ChildFailures收集原始错误，主流程在所有注册线程join后检查；普通执行器还检查完成Future的异常。专门演示execute异常的例子只有一次指定类型/消息是预期，其他异常仍失败。runner对正例拒绝非预期异常诊断并要求每个结果/清理/最终成功标记恰出现一次；交互诊断也使用同样的完整性原则。

修复回归命令为 `python3 verify_revision.py`，输出 proof/run-r4 和 proof/r3-regressions，要求目录尚不存在；顺序运行，不覆盖证据。五个源码变体分别在atomic加一后、busy清理期间、普通executor完成A后抛异常，以及改变Future失败cause、普通FutureTask完成副作用后失败，均须runner非零、result=fail、包含准确原因并已结束线程。源码注入回归也有资源期限，不将编译/启动失败当目标故障。这个命令会启动JVM。纯文本/静态核对仍为 `python3 check_evidence.py`。

## 清理失败也不能改写主因

PoolCleanup 先 countDown，再 shutdown 和最多3秒的 awaitTermination，真正超时才 shutdownNow 并再次有界等待；强制停止本身是一条清理失败。try-with-resources 保持场景原主异常，清理异常由语言规则追加suppressed；主流程再合并不同的子异常。ChildFailures按Throwable身份去重，并避免把已存在于主异常cause树里的对象再次加入。

HarnessContracts用真实有限线程池观测shutdownNow调用次数：协作完成必须为零，故意不给单worker放行才经过3秒超时并恰强停一次。它检查主Throwable身份、独立清理异常、同Throwable只出现一次和不同Throwable均保留。不是重复跑到成功的概率测试。proof/history/r2-review保留上一版真实失败的原始Java输出和对应源身份；原jcmd失败也继续保留。
