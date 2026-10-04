# PRJ-04-A08-P01：Project 归档持久幂等前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A08-P01。输入：冻结 `PROJECT_ARCHIVE` 的 S,L,C,I,M,A 控制、PRJ-01-A06 内部单向归档、通用收据 Migration `0015`；决策 `DEC-20260925-060`。
- Changed：内部归档新增同事务幂等入口。当前 Session、License、加锁后的 ProjectManager/成员/部门事实均需有效；同 Key/同版本重放返回已归档结果，不再次写 Project 或 Audit；异版本冲突。保留原内部 `archive()` 兼容路径。
- Files：Project 归档服务/写仓库/授权服务、单元与临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无新增；目标库须已有 `20260925_0015`。API：无公开路由；冻结 `/api/v1` 合同未变。
- Tests：Windows 11/Python 3.13 后端 395/395 PASS；PostgreSQL 18 临时库同 Key 两线程并发仅一次归档/Audit/收据、异版本冲突、新 Key 归档拒绝、Audit 失败时 Project/收据回滚 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：内部归档幂等前置 PASS；公开 HTTP、Windows 显式平台接线、PRJ-04 整体、Gate 3 与可用程序包未完成。
- Known Issues：正式发行信任源、Windows Server 2025/HTTPS 和 Debian 13 未验证；归档后其他模块新写/Job 的拒绝仍需各模块验收。
- Next：PRJ-04-A08-P02 归档 POST 的严格 HTTP 边界与同 Key 合同验证。
