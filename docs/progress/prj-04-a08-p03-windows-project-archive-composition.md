# PRJ-04-A08-P03：Windows 显式平台 Project 归档组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A08-P03。输入：P01 内部持久幂等、P02 可选 HTTP、Windows 显式平台组合；决策 `DEC-20260925-062`。
- Changed：仅在 `--platform`/`--platform-write` 既有 Schema/License/游标信任源前置通过后，给 Project 写服务注入 `0015` 收据并挂载归档 POST；默认登录模式仍 404。
- Files：Windows 组合根、组合契约/临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无新增；目标库需已有 `0015`。API：挂载冻结 `POST /api/v1/projects/{project_id}:archive`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 398/398 PASS；默认模式 404、显式平台无信任源失败关闭；PostgreSQL 18 临时库真实 Session/Project SQL 首次归档和同 Key 重放均 200、仅一次 Audit、合成 License 拒绝 403；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：Windows 显式归档组合和隔离合成端到端 PASS；正式发行信任源、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS、Debian 13 未验证；归档后其他模块新写/Job 禁止须随模块逐项验收。
- Next：PRJ-04-A09 预检并逐项接入 Project Member 管理 HTTP；优先成员列表安全投影。
