# PRT-01-A11-A05-P04-P01：20并发资格读取预检

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p04-read-load/verify.py'
```

脚本在Windows11隔离PG18.6/pgvector中经正式服务建立批准Requirement、Prototype/Review/Trace、真实Document文件及完整Link，然后对两项Prototype资格各先预热一次，再各做三轮同时发起20个ASGI GET，记录每轮单请求耗时的min/P50/近秩P95/max及三轮P95中位数，要求每个响应状态、ETag和阶段均正确。另测20并发`/health/live`对照；在同一数据上仅为诊断创建20+0连接池的第二运行时，测完即释放，生产默认不变。此预检复用真实Owner、数据库与磁盘，但不是Uvicorn网络服务、发行账户或20个独立项目的正式性能验收；测值必须保留环境与作用范围，不得把单次低于阈值直接报告为正式SLA PASS。退出时清理本轮PG实例、随机库及Temp目录。
