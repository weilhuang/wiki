# 请求在等什么，以及断言如何被反例检验

这是原创教学应用代码，不是 Python、Linux、HTTP 服务或数据库的源码节选。
运行证据固定于 CPython 3.12.14 / Linux，依赖只有标准库；未安装任何软件。

## 运行

在本目录内：

```sh
python3 --version
python3 -B verify.py
python3 -B causal_walkthrough.py
```

`verify.py` 使用当前 Python 启动有超时的有限子进程。每个子进程最多一个工作线程，无忙等、sleep、外部地址或固定端口；TCP 仅绑定 127.0.0.1，由 OS 分配端口。线程事件、锁、队列、socket 等待有 3 秒上限，join 有 4 秒上限，子进程有 15 秒外层上限。超时属于实验基础设施失败，不能当作预期反例通过。

结果包含完整业务结果、副作用、清理前后快照、退出码及源码 SHA256。CPU 用 100000 项固定整数计算，没有 CPU/延迟阈值。loopback 会真正建立 TCP 连接；事件与可读性观察不证明线程当时已进入内核睡眠。

## 文件

- waiting.py：有限计算、已持有的锁、空队列和 TCP 接收等待
- service.py：内存教学任务，清理资源由布尔值模拟，两个事件让测试暂停在提交和清理之前
- assertions.py：结果/调用副作用/取消顺序/完成发布/资源结束断言，失败时先记录状态，再做兜底清理
- verify.py：精确核对目标失败的子进程执行器；启动异常、错误退出码、错误原因及缺字段均不能假绿
- causal_walkthrough.py：正文同字节的可运行取消先到示例
- versions.json：运行版本与依赖范围
- source-manifest.json：除清单自身外的全部源文件 SHA256

## 单独看一个错误实现

```sh
python3 -B assertions.py duplicate commit-first
```

预期退出 1，status=rejected，violations=["SIDE_EFFECT"]，结果仍为 receipt:7 但 effects 有两项。此处非零才是目标实现错误被检出；其他非零不能自动算通过。startup-error 的退出 2/status=error 另行记录，不当作反例命中。

`correct` 只表示本教学任务在 cancel-first/commit-first 的指定正常路径满足断言。它没有生产级超时/异常恢复实现，资源是内存状态，不是文件描述符、事务或数据库连接。外层救援清理是实验安全措施，不是被测实现正确的证据。不能把该模型用来证明真实服务取消、持久化或内核调度性质。

所有源代码与说明以随附 MIT LICENSE 发布；包内没有复制上游 Python/Linux 源码。

## r2 验证器回归

运行 `python3 -B verify_regressions.py`，在独立临时目录分别制造：清理许可后提前发布done、中间结果错误而最终恢复、启动异常身份被替换。每项都必须使强化后的验证器因对应原因失败；源语法错误或无关异常不能冒认业务反例。原任务service.py与真实等待waiting.py保持原字节，r1遗漏保留于原冻结记录。

完整verify现在在computed时核对结果/副作用，并同步观察每次done.set调用前的资源状态。leak同时违反发布与资源释放两项承诺，预期原因列表为PUBLISH_ORDER、RESOURCE；列表必须完全匹配，不接受任意非零退出。控制方join后再检查最终状态，兜底清理不能擦掉已经观察到的泄漏。
