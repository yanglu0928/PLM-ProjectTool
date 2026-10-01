# WFL-01-A06-P01：Workflow 首阶段原子启动持久化

2026-10-02 / Phase 2 / `INTERNAL_PERSISTENCE_PASS`。编码前检查：Gate 2、六阶段定义 V1、Schema 0030、实例初始化/受权 GET 已具备；仅处理 Workflow 自有根与首阶段 NOT_STARTED→ACTIVE/HANDOVER 的事务内变更。输入为已核验的 ProjectId/expected_version/调用方事务；当前 WBS 不新增公开路径、角色、实体、迁移、依赖、License 或 Gate 判定。权限由后续 Application Service 在同一事务完成，本 Repository 不能直接接 HTTP。

实现：新增 `SqlAlchemyWorkflowStartRepository`。先独占锁住 Workflow 根，再读完整固定定义快照，拒绝缺失、旧版本、已启动、定义指纹不匹配或不完整初态；同事务仅把首 Stage 改 ACTIVE、根改 ACTIVE/HANDOVER、lock_version 0→1，重新读取完整投影核对。无隐式初始化、无 checklist PASS、无 StageTransition/Gate/Review/Audit 写入；不自行 commit。`DEC-20261002-597` 记录结构选择和回滚边界。

验证：Windows11/Python3.13/一次性 PostgreSQL18.6 `validation/wfl-01-a06-p01-start-repository/verify.py` 真实空库至head、初态/缺资源/版本与状态冲突、无 commit 回滚、提交后六阶段和十二清单、双写者仅一次启动、无 Gate/Checklist Record；脚本退出0，临时集群停止、目录清理、55432无监听。新输入单位2项；后端全量1816项通过、3项既有环境跳过。首次全量测试发现根选错产生29个相对导入错误，改以 `apps/backend/tests` 为包根重跑全过，未改产品代码。开发wheel SHA-256 `daa21d924de6728ed10920716922bb050946ca8ef15debaa55f18819ad81df88`，非发行包。既有 Alembic 计算列 default 警告保留，`command.check` 无新操作。

兼容/升级/回滚：无本轮 Migration/API/依赖变更；需既有0030及之后 Schema。未装配公开入口时可撤 Repository，已真实启动的历史不得静默回退。正式 License/目标账户、受权命令/原始幂等回执/Audit、HTTP、首阶段业务 Gate、Server2025/Debian、性能/UAT/Gate3仍未完成；本项不能当项目交接已通过。下一项 `WFL-01-A06-P02` 当前权限与幂等原结果下的受权 Workflow 启动命令，再分别做HTTP/Windows组合。
