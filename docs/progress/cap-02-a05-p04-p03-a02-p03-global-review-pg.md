# CAP-02-A05-P04-P03-A02-P03：GLOBAL Capability Review 隔离 PG 决定闭环

日期：2026-10-24；状态：`WINDOWS11_SYNTHETIC_PG_PASS / HTTP_AND_BROWSER_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A02-P03`；只验此前未装配的 GLOBAL Review 读取/决定服务与 Capability Owner 在真实 PostgreSQL 18 的原子链。|
|基线与前置|`CR-CAP-005`、A02-P01/P02 单元通过、既有 CAP-01 送审和终态夹具；全部为合成账户/文档/Evidence，不使用客户数据。|
|数据库/权限|沿用原隔离 PoC PostgreSQL 18 目录，在 loopback `55434` 启动；每轮新建 `cap01a04a03_` 临时库并在脚本 finally 删除，不接正式业务库。启动前服务为停止态，结束后恢复停止态。|
|验收|当前普通受分配 Reviewer 读取与决定，管理员非分配拒绝、License/停用用户/撤 Evidence 拒绝、同号重放/漂移冲突、最终 Review/Capability/Audit/收据及批准指针一致，失败无额外决定或残留库。|

新增仅在 `PLM_CAP_GLOBAL_DECISION_VALIDATION=1` 时启用的验收模式与独立入口。沿用既有 CAP-01 真实 Schema 迁移、固定 GLOBAL 文档/Evidence、管理员送审、Review 两人决定及历史批准/退回/撤回夹具；新模式改为调用内部服务，并读取首轮与终态快照。失效合成 License 拒绝后同 Key 可成功，首次非终态决定同 Key 回放不重复，正文漂移 `CONFLICT_IDEMPOTENCY`；非分配管理员和停用评审人均拒绝。最终决定前撤销 Evidence，命令失败且 PG 决定数仍为零；恢复合成资格后同 Key 完成 `APPROVED`，Review ETag `v3`、版本指针和既有终态历史断言通过。

本轮执行两次均退出 0；第一次尚未打印新模式独立标记，新增明确标记并补非分配管理员、License 负例后同库脚本第二次退出 0，出现 `CAP_02_A05_P04_P03_A02_P03_GLOBAL_REVIEW_PG_PASS`。Alembic 既有向量索引/计算默认比较警告仍在，`command.check` 两次均为 `No new upgrade operations detected`。清理核查 `cap01a04a03_%` 临时库为 0、其他客户端为 0；PoC PG 服务按起始状态停止。未创建或清理任何客户数据。

本片只证明 Windows 11 合成隔离数据库的内部链；尚无公开 HTTP、Windows 生产组合、Edge 用户决定、真实人工审核或正式信任/离线安装证据。Gate/Pilot/Release 均未通过。
