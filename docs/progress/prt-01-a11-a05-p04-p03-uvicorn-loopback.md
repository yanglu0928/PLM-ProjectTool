# PRT-01-A11-A05-P04-P03：Uvicorn loopback并发读取

2026-10-08 / 状态：`NETWORK_FUNCTIONAL_PASS_PERFORMANCE_PRECHECK_FAIL`。

编码前检查：P04-P02已完成共享锁/撤权等待与后端回归，仍不达非AI GET P95≤500ms。CR-PRT-005保留偏差；本项仅扩展隔离验证工具，真实Uvicorn监听随机127.0.0.1端口，不改生产服务、API、Schema、权限或连接池。测试客户端显式`trust_env=False`，避免本机代理把loopback请求变成空502；保持受测应用原有Host校验。结束停止Uvicorn和PG，保留生产入口关闭。

Windows11/隔离PG18.6/pgvector、合成批准Requirement与Prototype、真实Review/Trace/Document文件/Link下，网络两项资格各预热并做三轮20并发GET；所有响应200、强ETag及PROTOTYPE阶段正确。近秩P95三轮中位：`PROTOTYPE_SCOPE_DECISIONS`710.31ms，`PROTOTYPE_COVERAGE`714.07ms；20并发`/health/live`对照83.28ms。ASGI同轮约741/760ms，诊断20+0池ASGI约719/677ms。网络链不达500ms。另重跑P03隔离用例：跨项目Link拒绝、成员暂停后资格/Checklist均404且无历史，恢复后继续通过。

这不是发行账户、正式信任源、多项目或Server2025性能验收；Debian13按用户指令跳过。无数据迁移，撤验证工具即可回滚，业务历史不变。剩余约77条SQL/资格请求与文件物理证明成本仍需定位并按CR最小优化；P04、Gate3和可使用包不能标PASS。
