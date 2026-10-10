# PRT-01-A11-A03-P01：Prototype 范围决定事务锁与四方一致性

日期：2026-10-08。状态：内部锁定输入通过；`PRT-01-A11-A03` 聚合 Owner 尚未通过，Workflow 两项仍关闭。

编码前检查：Phase 2/Gate 2 冻结基线及 `CR-PRT-005` 已核对；前置 A11-A02 纯范围策略已通过。本项仅涉及 Prototype 应用域的 NOT_REQUIRED 事实校验和基础设施事务读取，不改 DB Schema、冻结 `/api/v1`、权限或其他模块写路径。验收是当前项目行共享锁、全部 Prototype 根/决定/固定需求引用/不可变结果行在同一事务内读取，并拒绝陈旧、跨项目、缺结果、缺引用、指纹篡改与未定义状态。风险是锁粒度和不完整事实误判；回滚为停止装配该只读适配器，历史不变。

实现：先锁 ProjectRow 共享行，利用所有受权 Prototype 写操作的排他 ProjectRow 锁建立插入/变更围栏。按项目完整扫描四类行并加共享行锁；ACTIVE 根不得已有 NOT_REQUIRED 决定；NOT_REQUIRED 根必须有唯一决定和结果，且固定引用按序连续、无重复、与结果一致，根状态/锁版本/确认人/名称/Review 对与原命令摘要一致。ARCHIVED/RESTRICTED 暂无已冻结的范围解释，当前失败关闭，不静默排除。当前批准需求、Version/Review/Evidence/Artifact/Link/Trace 和 Audit 尚未由此证明；此输入绝不独立生成 Workflow PASS。

验证：定向 10 项、3 个子例 PASS；后端全量 3218 项 PASS、3 项条件跳过、4791 个子例 PASS。pytest 9.1.1 仅补入本机既有后端虚拟环境作为测试工具，未加入产品依赖或仓库。当前尚无该适配器真实 PostgreSQL 组合验证，保留给 A11-A03 后续聚合 Owner/真实数据库验收；不能标记 A03 PASS。

TraceLink：`CR-PRT-005` → `DEC-20261008-1073` → `PRT-01-A11-A03-P01` → A11-A03 后续 Owner → A11-A04 Registry/HTTP → A11-A05 PG/HTTP。
