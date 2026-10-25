# PRT-01-A11-A05-P04-P11：20并发请求网络时间线

2026-10-08 / 状态：`DIAGNOSTIC_COMPLETE_PERFORMANCE_FAIL`。

编码前检查：Phase2；输入为P10阶段计时和Windows11隔离PG18.6/pgvector、正式合成Approved Prototype/Review/Trace/本地文件链；仅改隔离验证脚本。用合成探针ID记录客户端开始、最外层ASGI进入、最后响应体发出、客户端完成四个时间点，原状态200、强ETag及阶段断言不变；不改生产程序、API、Schema、权限、数据库池或文件/Review证明。风险是客户端和Uvicorn仍在同一Python进程不同线程，GIL、Windows loopback和httpx调度可能影响进入ASGI之前的测量，不能外推正式发行SLA。

两次真实Uvicorn loopback/20并发/三轮，第二次每项60个业务样本及60个健康对照：`/health/live`进入ASGI前P50/P95约38/117ms、ASGI内约0.20/0.45ms、响应发出后约12/19ms。`PROTOTYPE_SCOPE_DECISIONS`进入ASGI前约278/502ms、ASGI内约64/87ms、响应发出后约53/72ms；`PROTOTYPE_COVERAGE`约275/487、66/99、52/76ms。业务端到端P95约564/575ms，仍超500ms；第一次业务进入ASGI前P95约494/502ms、ASGI内约90–96ms、端到端约569/589ms。各阶段P95属于不同请求，不可相加。工具均退出0、原PG/临时实例清理；未运行新后端全量（沿用P09的3253/3/4795）。

结论：当前本机同进程压测里最大观察区间是客户端发起到ASGI进入，而非Prototype Owner SQL/文件段；健康请求前段明显较短，说明不是固定loopback延迟。尚无法区分同进程客户端/服务端争用、连接建立/复用、Uvicorn接入与业务负载对事件循环的间接影响；不能据此改变生产池或放宽500ms。下一项用**独立客户端进程**重复同样的20并发网络测试、保持请求与安全断言一致，并单列启动开销以外的每轮P95。若独立进程仍失败，再定位服务端接入/线程等待；若通过也只证明本机隔离环境，不等于三平台或发行SLA。无迁移；撤探针包装可回滚，生产入口/Gate3继续关闭/阻塞。
