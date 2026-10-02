# HashMap JDK 21 最小实验

本包配合《HashMap 的查找、冲突与扩容》和《沿 OpenJDK 21 源码追踪 HashMap 的状态变化》。先读知识页再按问题运行，不需要先看验证日志。

## 运行

需要你已安装的 JDK 21，以及 Bash、grep、diff、tee。无 Maven、外部 Java 库、网络请求、容器或服务；不安装或修改工具链。

```bash
export JAVA_HOME=/你的/JDK21
bash run.sh api
```

也可只手动编译并运行，不使用 Bash 验证器：

```bash
mkdir -p classes
"$JAVA_HOME/bin/javac" -encoding UTF-8 --release 21 -d classes experiments/src/*.java
"$JAVA_HOME/bin/java" -cp classes HashMapWalkthrough
"$JAVA_HOME/bin/java" -cp classes HashMapLab --api
```

Windows 可按同样顺序使用已安装 JDK 的 javac/java；本次没有验证 Windows 命令行适配。

验证器编译后会运行主文的完整调用示例，并与 expected-walkthrough.txt 逐字对照；随后运行 7 个公开 API 场景并对照预期输出。断言使用显式检查，不依赖 JVM 是否启用 `-ea`。

- `bash run.sh api`：基础场景。可变键与错误 hash 契约是故意违约反例，只描述本次输入下的实现结果
- `bash run.sh impl`：基础场景加 4 个实现观察。通过公开 Entry 的 `getClass().getName()` 观察 Node/TreeNode；没有访问私有成员，不需要反射或 `--add-opens`
- `bash run.sh verify`：以上全部，再运行 5 个故意错误的假设。每项必须以 `java.lang.AssertionError` 作为主异常，首行包含对应的 `ASSERTION_FAILED: wrong hypothesis …` 命题且退出 1；仅带相同文本的其他异常也会被拒绝；任意编译错误、无关异常或反向用例成功均不算通过

默认产物位于 `experiments/.run/`，每次会覆盖其中同名文件，可用第二个参数指定独立输出目录：

```bash
bash run.sh verify "$PWD/my-run"
```

这只会创建/写入指定输出目录及其中的 classes 子目录，不操作你的业务数据。没有后台服务和需要停止的子进程。完成后可自行删除这次输出目录；不要把重要文件放入该目录。

## 能观察到什么

| 入口 | 输入变化 | 核心断言 |
| --- | --- | --- |
| identityAndCollision | 相等新对象；同 hash 不等对象 | 更新返回旧值且不增加 size；碰撞保留两条映射 |
| mainTraceAndBitModel | A/B/C/D 的散列 1/5/9/13 | 四条映射保留；独立计算的 4/8 桶索引分别为 1/1/1/1 与 1/5/1/5 |
| brokenContract | equals 相等但 hashCode 不同 | 此固定实现查不到另一个违约键，不把违约行为当 API 保证 |
| mutableKey | 插入后 id 从 1 变 2 | get 失败但 size 仍为 1；正确移除后改变身份再插入可读 |
| nullAndUpdate | null 值、缺键、null 键与 computeIfAbsent | containsKey 区分 null 与缺失；null 计算结果不创建映射 |
| iteration | 创建迭代器后同线程新增 | 确定操作在 next 时检测到错误；iterator.remove 与 Entry.setValue 正例有效 |
| presizing | newHashMap(13) | 13 条映射可读，不声称实测容量或扩容次数 |
| implPutThreshold | 容量请求 64，同 hash，连续 put | 第 8 条后 Node，已有键更新仍 Node，第 9 条后 TreeNode |
| implDefaultGrowth | 无参构造，同 hash，连续 put | 第 8/9/10 条后 Node，第 11 条后 TreeNode；具体容量来自源码推演 |
| implComputeThreshold | 容量请求 64，7 个旧键后 computeIfAbsent | 返回值为 8、size 为 8、全部 8 项 value 正确，且每项为 TreeNode |
| implTreeSplit | 6 个 hash=0、7 个 hash=64，另加 36 个键 | 49 条映射全部保留，拆分后 6 条为 Node、7 条为 TreeNode |

## 反向断言

`HashMapLab.java` 中的 `negative` 方法完全可见，没有隐藏测试。五个错假设分别是：

1. equal-adds：相等的新对象应该新增一条映射
2. collision-overwrites：不同键只要完整 hash 相同就应该覆盖
3. mutable-stays-readable：改掉键身份后用原引用必能查询
4. eighth-put-tree：容量请求 64 时，第 8 个普通 put 就必树化
5. resize-keeps-every-index：容量 4 → 8 时 B 的索引应该保持 1

它们是教学命题的反向检查，不是对 JDK 二进制做变异测试。第 5 项检查本文明确的位运算模型，没有读取私有桶数组。

## 版本与证据边界

源码基线是 OpenJDK `jdk-21+35`。本次执行二进制为 Temurin `21.0.12.1+1-LTS`，Linux x86_64，`javac 21.0.12.1`。运行工具链 src.zip 的 HashMap.java 与固定 GA 文件字节相同，SHA256 为 `71c8d82247c2736e9fbe3769f366e9bd250bc73ecf390749998e830201aaabf2`；不因此声称执行过 GA 二进制。

公开 API 模式和可选类型观察均通过；完整验证器退出 0，5 个反向假设各自预期退出 1。R2 见 `verification.json`、`proof/run-r2-20261002/` 及命令输出。R1 曾漏检错误异常类型及 compute 的错误返回值，原失败证据保存在 `proof/r1-independent-failures/`，修订见 `REVISION-R2.md`。重跑日志默认另写入 `.run/`，不会覆盖已保存的首轮证据。

没有测试性能、并发交错、旧 JDK 7 并发扩容、对象内存大小、树颜色/黑高、私有容量字段或所有删除顺序。测试只观察接口返回、映射保持和明确标识的 Entry 实际类型，不能证明全部 HashMap 性质。

## 可选：检验验证器本身

若要重跑 R2 新增的回归，还需 Python 3（只用标准库），沿用同一个 JAVA_HOME：

```bash
python3 tools/check-regressions.py
```

它在临时目录复制本包的教学实验，对七个具体缺陷分别做变异并要求验证器拒绝。不会修改原实验或 JDK，结束时自动清除临时编译目录；结果写到 `proof/r2-regressions/`，会覆盖该目录里的同名回归记录。如需保留首轮记录，先复制本包到新的目录再跑。普通 `api`/`impl`/`verify` 不需要 Python。

本次七个隔离变异均以目标故障证据退出 1，全部被拒绝；R1 被漏过的两个变异现在都不再通过。详见 `proof/r2-regressions/results.json`。

## 文件与来源

- `docs/`：两篇知识文章候选 Markdown
- `experiments/src/`：可运行教学代码和全部断言
- `sources/`：固定 OpenJDK 源码、实际工具链同文件副本、历史对照、许可
- `sources.json`：官方来源、版本和版权说明
- `snippets.json`：代码摘录范围；`tools/check-content.mjs` 为编辑检查，需现有 wiki 工程的 Code Hike/Mermaid 依赖，不是基础实验的运行要求
- `proof/`：已执行输出和静态检查结果，不含编译出的 class 文件

Code Hike 的 !step 只用于文章，完整调用示例与运行文件逐字同步。三段上游方法摘录是类内部片段，不可单独编译。

上游 OpenJDK 文件保留原版权头与 GPL v2 + Classpath Exception 许可；请同时保留 `OPENJDK-LICENSE` 与 `OPENJDK-ADDITIONAL_LICENSE_INFO`。文章说明和教学调用代码为本次原创，不复制参考知识站的正文或图。历史 JDK 7 文件仅用于源码对比，未运行。
