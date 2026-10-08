# PRT-01-A11-A03-P03-A02：Requirement 当前验收标准稳定引用公开证明

日期：2026-10-08。状态：内部公开 Port 验证通过；Prototype Workflow Owner 尚未完成。

编码前检查：承接 `CR-PRT-005` 完整 Requirement 左侧范围和 A11-A03-P01 项目锁围栏；本项只在 Requirement 模块提供当前 Approved RequirementVersion 的验收标准稳定 UUID 引用，不改 Schema、冻结 API、权限、正文或写操作。调用方必须在同一事务中先持有完整项目范围锁，后续还要比较 Requirement Owner 的正式资格快照，不能仅凭这些 ID 判定 PASS。

实现：公开 `RequirementAcceptanceRefsProofPort` 和严格 Proof DTO；适配器共享锁定当前 ACTIVE 根、正式批准版本和有序验收标准行，要求当前指针精确、Review 绑定存在、声明数量等于实际行数、零基序号连续、引用非空且不重复。缺失、过期或跨项目输入失败关闭。只返回 IDs，不跨模块导出 ORM 或客户正文。

验证：定向 6 项覆盖完整顺序、空/缺失/不连续、重复稳定引用；后端全量 3230 项通过、3 项条件跳过、4791 子例通过。真实 PostgreSQL 组合与 Prototype 聚合 Owner/HTTP 留后续。兼容性/升级/回滚：无 Schema、API、生产依赖或迁移；停止装配公开 Port 可回滚，历史不变。

TraceLink：`CR-PRT-005` → A11-A03-P01/P02 → 本公开证明 → A11-A03 聚合 Owner → A11-A04 接线 → A11-A05 PG/HTTP。
