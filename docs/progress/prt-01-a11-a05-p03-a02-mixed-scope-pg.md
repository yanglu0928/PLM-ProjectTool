# PRT-01-A11-A05-P03-A02：批准原型与 NOT_REQUIRED 混合范围

日期：2026-10-08。状态：`PRT_01_A11_A05_P03_A02_MIXED_HTTP_PG_PASS` 与 `PRT_01_A11_A05_P03_A02_CONFLICT_HTTP_PG_PASS`；限Windows 11隔离PostgreSQL18.6/pgvector合成场景。

编码前检查：Phase 2/Gate 2冻结架构、Schema和API不变；前置Requirement→PROTOTYPE真实链、Prototype物理文件、全NOT_REQUIRED与单需求Approved Prototype均通过。本项仅拓展多Requirement混合范围的正式Owner/HTTP/PG验证，不开启生产入口。涉及Requirement、Review、Prototype、Document、Workflow及Audit；ProjectManager命令和CustomerManager评审均用合成身份，不冒充客户事实。风险是测试夹具直接伪造APPROVED、在阶段推进后追加需求、只测预览不测写时漂移；依据`DEC-20261008-1076`在REQUIREMENT阶段完成两个正式审批，并复验Checklist两个Review轮次。

正向链：两条当前批准需求同一Project，一条固定在当前Approved PrototypeVersion及真实Document文件中，以ACTIVE/VALIDATES Link覆盖唯一验收标准；另一条由PM执行固定版本的NOT_REQUIRED决定，正式Audit必须存在。缺决定时两项资格均409。补齐决定后两项资格返回一个PRT-03及两个REQ-03当前受审主体；预览后篡改文件，首次Checklist写仍409，恢复原字节后两项PASS并推进SOLUTION/v13。另一次独立随机库建立同一需求被Approved Prototype与NOT_REQUIRED同时认领，资格409且Prototype Checklist记录为0。两轮均迁移到当前head、Alembic drift无新增操作并清理随机库、PG实例和本轮Temp目录。

兼容性/升级/回滚：只修改验证脚本、测试结构决策和文档；无生产代码、Migration、API、权限或依赖变化，无升级步骤，撤测试扩展可回滚。Alembic既有向量表达式/计算默认值比较警告保留。该证据仍不覆盖多原型重叠、部分验收标准覆盖、跨项目、撤权与20并发，也不证明Server2025、正式信任源、客户真实UAT或生产开关可开启。Gate 3仍BLOCKED。

TraceLink：`CR-PRT-005` → `DEC-20261008-1076` → A05-P02/A01真实单分支 → A05-P03-A02混合/冲突隔离PG证据 → 后续复杂负例/并发/生产入口。
