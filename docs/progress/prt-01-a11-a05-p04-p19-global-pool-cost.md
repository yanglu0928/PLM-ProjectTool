# PRT-01-A11-A05-P04-P19：GLOBAL Review读取与剩余连接成本

2026-10-08 / 状态：`GLOBAL_READ_PASS_PERFORMANCE_FAIL`。

编码前检查：Phase2；输入为P18共享Review仓储JSONB类型还原及两轮性能未达标、CR-PRT-005。只扩隔离验证工具：在现有一次性PG18.6上运行独立GLOBAL Review合成库，并将生产默认池5+10的`connect`路径计时与原临时20+0池对照。不改生产Review、连接池、Schema、API、权限或客户数据。目标是证明GLOBAL的`project_id=NULL`、双评审批准和撤回轮次读取，及识别默认池取得路径成本；路径包含等待/预检/新建，不能独立解释为纯队列等待。

GLOBAL验证：隔离脚本退出0。真实PG中的合成GLOBAL Review由两位Reviewer正式批准，另一轮撤回；共享`SqlAlchemyReviewSnapshotReadRepository.get_round`逐轮返回`scope=GLOBAL`、`project_id=None`、批准轮两项Decision及正确WITHDRAWN状态。原GLOBAL提交/审批/撤回/Audit/主体终态及PROJECT Workflow链均继续通过；临时数据库和实例按原脚本清理。该范围不证明所有真实客户规模及Server2025。

性能诊断：Review合并后同一Windows11隔离库/文件、独立客户端20并发、默认→临时20+0→默认交错三轮均退出0，HTTP200/强ETag/阶段断言不变。临时池两项（Scope Decisions/Coverage）P95约480/492、476/486、511/486ms；默认前约504/510、501/511、510/500ms，默认后约524/505、526/501、530/502ms。临时池两轮两项低于500ms，但第三轮首项约511ms，不能标稳定达标。默认池244次连接取得路径P95约133/144/134ms、临时20池约9.7/10.3/9.6ms；两者明显不同，但路径同时覆盖预检/新建且默认后段安装探针、默认前段未安装，不能将全部差值归因池排队。每资格仍约48条SQL，Review/Requirement/文件与调度成本仍在。

决策：保留生产默认池5+10与关闭的Prototype入口，性能/Gate3/UAT/可用包继续FAIL/BLOCKED。P20先评估目标实例PostgreSQL最大连接数、服务进程/Worker数、单连接内存与其他连接消费者，再设计可回滚的受控池参数；仅在资源预算、失败关闭与重复业务P95证据满足后实施配置变更。即使Win11达标也不等于Server2025/发行通过。无生产迁移；撤探针可回滚。

TraceLink：CR-PRT-005 → P18 → P19 → DEC-20261008-1092 → P20。
