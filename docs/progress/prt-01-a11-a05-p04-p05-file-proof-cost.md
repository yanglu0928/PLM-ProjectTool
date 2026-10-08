# PRT-01-A11-A05-P04-P05：文件物理证明耗时定位

2026-10-08 / 状态：`MEASURED_SQL_REMAINS_PERFORMANCE_PRECHECK_FAIL`。

编码前检查：P04-P04将Requirement范围重复扫描消除后，Uvicorn网络20并发P95仍约594/632ms，高于500ms；现有真实文件校验必须保留。CR-PRT-005先记录只能做测量、不跳过证明。仅隔离验证工具以计时子类调用原`LocalFileStorage.verify_content`，生产代码、API、Schema、依赖、连接池与权限不变；撤计时包装即可回滚，无数据迁移。

Windows11隔离PG18.6/pgvector、合成小文件与正式Owner/Review/Trace/Link下，122次网络资格请求（含预热）的文件证明逐次实际执行：P95约10.49ms、总耗时约632.40ms；同轮两项Uvicorn三轮20并发P95约618.01/616.35ms，全部200、强ETag及PROTOTYPE阶段正确。ASGI内进程默认池文件P95约50.44ms、诊断20+0池约71.90ms，说明调度/主机负载会影响计时，不能拿本轮数字作为发行磁盘SLA。网络测试中该小文件的物理校验不是主要超标来源，禁止删除或缓存绕过。

剩余约63条SQL/请求和多Owner完整证明更值得诊断；本项没有优化生产路径，也未达到500ms。Server2025未运行、Debian13按指令跳过，生产Prototype入口/Gate3/可用包继续关闭。
