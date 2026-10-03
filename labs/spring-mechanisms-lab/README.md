# Spring mechanisms lab

固定 Java 21、Spring Framework 6.2.19、Spring Boot 3.5.16。用真实非 Web 上下文检查代理分派与自动配置；没有数据库、Docker、Web 端口、外部服务或后台业务任务。

## 运行

需要 JDK 21 和 Python 3.10+。先设置 JAVA_HOME 指向 JDK 21。JAR 不随源码包分发；每个制品坐标、Maven Central URL、SHA-256、许可证位置在 dependencies.lock.json。

已有依赖可直接使用下面两种方式之一：

```sh
python3 run.py --deps-dir /your/flat-jar-directory --output proof/local-1
python3 run.py --gradle-cache /your/gradle-home/caches/modules-2/files-2.1 --output proof/local-1
```

若需要下载固定依赖，显式执行以下命令，再运行：

```sh
python3 prepare_deps.py --output deps
python3 run.py --deps-dir deps --output proof/local-1
```

prepare_deps.py 只向锁定的 Maven Central URL 下载并核对 SHA；本次已记录运行使用既有离线缓存，没有重新下载依赖。不要把准备依赖的网络耗时算进 Java 实验的运行预算。

Linux 上可以加最后一道外部时限：

```sh
timeout --kill-after=5s 85s python3 run.py --deps-dir deps --output proof/local-2
```

驱动内预算75秒、单子进程20秒，Java与javac各限堆64 MiB/ActiveProcessorCount=2，按顺序执行。超时或中断先终止子进程组，2秒仍未结束则强停，再回收；清理失败不会变绿，原始异常保留。编译产物属于临时目录，执行后移除。输出目录必须是新的，不能覆盖历史。

## 观察什么

AopLab 用 BeanNameAutoProxyCreator 包装真实容器里的 gateway。两种代理都检查目标与代理身份、单例身份、Bean数量、完整拦截器顺序、业务进入次数、异常同一引用、自调用与private边界。附加 ProxyFactory 检查 final 类上的 final 接口方法仍可通过 JDK通知，强制CGLIB时根因是不能继承final类，以及缓存短路必须使目标进入次数为0。

BootLab 用 ApplicationContextRunner 分别改变缺省/false属性、隐藏可选类、提供用户对象，检查类型、数量、身份、默认构造器次数和条件报告。依赖实验确认定义排序不等于构造次序，OnBean只观察当时定义；最后一个上下文通过实际EnableAutoConfiguration与本包imports资源发现候选。FilteredClassLoader隐藏的是本包可选标记类型，并非卸载依赖JAR。

三个具体错误分支：

- bypass-proxy：调用者错误地拿原始目标，结果仍正确但拦截器顺序断言失败
- proceed-on-cache-hit：缓存命中后仍执行后续链，结果/进入次数断言失败
- remove-backoff：自动配置缺少退让，产生两个实现，用户身份与数量断言失败

错误分支必须编译成功、启动到实际业务断言，准确顶层 main AssertionError 和退出码1同时匹配；编译错误、启动失败、同文本其他异常或普通子线程未捕获异常都不算目标反例成功。框架预期的 final 类拒绝在正常实验内捕获并检查外层和根因，完整cause会输出。

```sh
python3 check_classifier.py
python3 verify_evidence.py --run proof/run-3
```

check_classifier 是纯Python输出分类夹具，验证普通线程错误、编译/启动错误、错误类型、超时与清理失败不能伪装成功；它不是实时JVM故障注入，不证明所有操作系统清理路径。

## 记录与范围

- proof/run-1：首次真实执行；正常路径与三个反例通过。当时驱动只按准确主异常行和exit检查，内部预算85秒。原驱动原字节保存在 history/run-1/run.py，与记录SHA一致
- proof/run-2：驱动重新执行，保留75秒内部预算和严格失败分类。当次Java业务源码及依赖未改
- proof/run-3：缓存错误变体在执行目标后仍返回cached，准确测试结果相同但副作用增加的情况。旧AopLab源码保存在history/pre-cache-fix/AopLab.java，与run-1/run-2记录SHA相同
- proof/classifier.json：纯Python分类验证结果
- source-lock.json：官方tag源码原字节、路径、SHA和Apache-2.0许可
- snippets.json：正文摘录对应完整文件和行，统一去缩进，复制内容没有Code Hike注释

本包不验证完整SpringApplication、Web、Actuator、AspectJ、AOT/native image、父子容器、动态TargetSource、FactoryBean特殊类型、异步/响应式、性能和生产容量。成功进程退出及单个普通上下文的close，不等于证明所有资源供应商的销毁回调都可靠。

LICENSE用于本包教学源码；sources目录保留上游版权头，licenses目录保留依赖内原始license/notice。THIRD_PARTY.md说明外部来源。无二进制、缓存、工具链、账号数据或凭据随包发布。
