# Spring BeanDefinition 最小源码实验

目标：区分配置读取、定义注册、实例创建，验证名称/别名、延迟实例化和错误发生阶段。

## 运行

需要完整 JDK 21、Gradle 8.10.2；请确认 JAVA_HOME 指向 JDK 21。本项目没有 Gradle Wrapper，也不自动下载 JDK。

```sh
gradle --no-daemon --max-workers=1 clean check run
# 依赖已缓存时
gradle --offline --no-daemon --max-workers=1 clean check run
```

首次构建通过 Maven Central 取得依赖。`gradle.lockfile` 锁定运行与测试类路径版本；没有动态依赖版本。无需 Docker、数据库、额外JVM模块开放参数。

- 应用入口：`src/main/java/lab/Main.java`
- 应用输入：`src/main/resources/beans.xml`
- 可见断言：`src/test/java/lab/BeanDefinitionLabTests.java`
- 变体配置：`src/test/resources/*.xml`
- `check` 明确依赖 `verify`；后者是 JavaExec 测试驱动，不依赖 JUnit 或 JVM `-ea`
- 断言失败抛 AssertionError，导致 Gradle 非零退出；不是靠匹配控制台 PASS 文案判断通过

## 预期结果

13 个场景、61 条断言通过，随后主程序输出：

```text
registered: definitions=1, aliases=[catalogAlias], singleton=false, constructed=0
refreshed: singleton=false, constructed=0
looked up: label=alpha, same=true, constructed=1, initialized=1
closed: destroyed=1
```

覆盖策略测试会产生一条 Spring INFO 覆盖日志；这是明确设置允许覆盖后的预期动作。Gradle 8.10.2 可能打印废弃API通用提示，本工程没有声称兼容 Gradle 9。

## 13 个场景

1. 裸 reader 读 eager 定义也不会自动创建实例
2. lazy XML 上下文延迟创建；别名与主名得到同一对象；别名不是定义表键
3. eager Bean 在 refresh 返回前完成创建
4. eager Consumer 的依赖会促使 lazy Catalog 提前创建
5. 跨资源重复名称且显式禁止覆盖时失败，保留第一份定义
6. 跨资源显式允许覆盖时后定义生效，返回数量净增量0
7. 同一 beans 元素内重名，即便允许覆盖也被解析器拒绝；先前定义并不回滚
8. 格式错误 XML 在注册之前失败
9. 缺失 classpath 资源在打开输入流时失败
10. 未知属性能注册定义，但在属性填充阶段失败且不留下完成单例
11. 缺失 ref 在依赖解析阶段失败
12. BeanFactoryPostProcessor 修改定义后再影响对象
13. 注解入口在 refresh 中展开 Bean 方法定义，lazy 产物仍延迟创建

## 调试

用 IDE 导入 Gradle 工程并关联 Spring Framework 6.2.19 的源码，运行 Main。建议依次停在：

- AbstractXmlApplicationContext.loadBeanDefinitions(DefaultListableBeanFactory)
- AbstractBeanDefinitionReader.loadBeanDefinitions(String, Set)
- XmlBeanDefinitionReader.loadBeanDefinitions(EncodedResource)
- DefaultBeanDefinitionDocumentReader.processBeanDefinition
- DefaultListableBeanFactory.registerBeanDefinition
- Main 的 BeanFactoryPostProcessor 回调
- DefaultListableBeanFactory.preInstantiateSingleton
- AbstractBeanFactory.doGetBean
- Catalog 的构造器 / setLabel / init
- DefaultSingletonBeanRegistry.addSingleton（beanName == catalog）

Watches 不要调用 getBean，否则调试器可能自行触发实例化。计数器是单线程实验探针，不是并发监控工具。

## 范围

只验证普通同步 XML 创建和一个最小注解配置，不验证 Boot、Web、AOT、后台初始化、循环依赖、代理、FactoryBean 产物、自定义 scope 或外部资源失败。源码文章的 Boot 3.5.16 部分仅是官方固定 tag 对照。

实际运行、工具链和依赖身份见 VERIFICATION.md；原始执行日志保留在 evidence/。
