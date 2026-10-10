# WFL-01-A03-P01 持久层前置设计

- Phase 2；来源：冻结 DM-02/SC-01/SC-02/API-02、配置 V1。当前分支 `feature/license-runtime-guard`；前一任务 c3e1ed5 已同步，工作区起始 clean。
- Changed：登记 CR-WFL-002，明确 BLOCKED/current、终态指针、既有项目初始化及最终完成 API 缺口；定义四表、复合归属、初态/完整性、只读定义和验收矩阵。
- Result：前置设计完成，Schema/ORM/Migration **未实施、未验收**。无 API/依赖/客户事实变化；正式数据库未操作。
- Tests：本任务不含运行代码变化，未新增/运行数据库或 API 测试；已有 616 项后端测试仅为上一任务证据，不作为本 Schema 通过证据。
- 风险：数据库完成路径、历史/权限/Gate 接线未具备；暂不挂载 Workflow 写 API。POC-03/生产信任源/目标平台既有发行约束不变。
- Next：WFL-01-A03-P02 按设计实施四表 ORM、0030 migration 和隔离 PostgreSQL 空/有数据升级、downgrade、事务约束验证。
