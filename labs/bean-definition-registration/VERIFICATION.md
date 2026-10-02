# 运行证据（2026-10-02）

## 最终结果

- JDK：Eclipse Temurin 21.0.12.1+1-LTS
- Gradle：8.10.2
- Spring Framework 实际解析：spring-context / beans / core / expression / aop / jcl 均为 6.2.19
- Micrometer observation / commons：1.15.12
- 结果：13 个独立可见场景、61 条断言通过；Main 的四行输出与README一致
- 最终命令退出码：0；最终 `clean check run resolvedVersions` 耗时6秒
- 运行模式：离线、单 Gradle worker、禁用持久 daemon；Gradle 使用的一次性 daemon 已退出
- 未启动数据库、网络服务、Docker或外部Spring Boot应用

## 实际命令

设 JAVA_HOME 指向已有 Temurin 21.0.12.1+1，PATH 中放已有 Gradle 8.10.2，GRADLE_USER_HOME 指向本次隔离缓存。执行目录为本工程根目录。

```sh
gradle --offline --no-daemon --max-workers=1 dependencies --write-locks --console=plain
gradle --offline --no-daemon --max-workers=1 clean check run resolvedVersions --console=plain
```

第一个命令生成 `gradle.lockfile`，第二个命令在锁存在时重新清理编译并验证，9个任务全部执行。首轮无锁的成功运行保留为历史，不重复算作额外测试覆盖。

缓存复用自本工作区之前的 Spring 独立审阅缓存，复制到独立 GRADLE_USER_HOME；没有复用旧的本项目class文件。JDK与Gradle复用已有工具链，没有重复下载重型SDK。依赖JAR的路径、版本和SHA256见 dependency-artifacts.json；依赖锁来自Gradle实际生成，没有手工伪造。

## 证据文件

- `evidence/toolchain.log`：java -version / gradle --version
- `evidence/dependency-lock.log`：实际生成锁的输出
- `evidence/verification.log`：最终clean编译、验证、main与解析版本输出
- `evidence/process-check.log`：执行结束后检索本任务Java/Gradle进程，结果为空
- `dependency-artifacts.json`：锁定依赖的字节身份
- `source-manifest.json`：本次受验证Java、XML和构建文件的相对路径与SHA256

记录时间为UTC 2026-10-02 14:00前后；JVM内置日志时间使用环境默认本地时区，因此日志中的22:00与UTC记录不同，不是另一轮运行。

## 解释限制

- 编译/运行通过不证明所有源码分支，尤其不覆盖后台初始化、FactoryBean、循环依赖、代理和AOT
- 名称唯一性、覆盖策略和“先注册后失败仍有定义”结论只针对测试中明确的配置与裸工厂；不推广为所有容器实现的事务合同
- 候选正文单独通过3段真实CodeHike编译/清洁代码/范围检查、3张Mermaid解析与可访问描述检查；浏览器渲染与独立技术审阅由整站验收另行提供
- Gradle打印通用废弃API提示，未声称Gradle9兼容
