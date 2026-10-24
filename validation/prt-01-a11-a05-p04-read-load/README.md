# PRT-01-A11-A05-P04-P01：20并发资格读取预检

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p04-read-load/verify.py'
```

脚本在Windows11隔离PG18.6/pgvector中经正式服务建立批准Requirement、Prototype/Review/Trace、真实Document文件及完整Link，先验证两个预览授权事务可共享行锁、成员撤权更新会等待，再对两项Prototype资格各预热一次并做三轮同时发起20个ASGI GET，记录每轮单请求耗时的min/P50/近秩P95/max及三轮P95中位数，要求每个响应状态、ETag和阶段均正确。另测20并发`/health/live`对照；在同一数据上仅为诊断创建会话/资格共用20+0连接池的第二运行时，测完即释放，生产默认不变。可加`--sql-diagnostic`收集无参数SQL模板的计数和耗时；默认不启用事件计时，以免污染性能测量。此预检复用真实Owner、数据库与磁盘，但不是Uvicorn网络服务、发行账户或20个独立项目的正式性能验收；测值必须保留环境与作用范围，不得把单次低于阈值直接报告为正式SLA PASS。退出时清理本轮PG实例、随机库及Temp目录。

使用`--network`时，附加启动本机随机端口的真实Uvicorn loopback，复用同一数据和Host策略做三轮20并发网络GET；客户端不使用系统代理。仍不代表正式发行账户、TLS、跨机器或多项目负载验收。

读取负载模式下使用仅验证工具的计时子类，仍逐次调用原本地存储的`verify_content`执行真实字节/Hash校验，分别输出ASGI默认池、诊断池及网络的文件证明耗时；该计时不改变生产类或安全规则。
