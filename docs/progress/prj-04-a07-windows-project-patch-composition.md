# PRJ-04-A07：Windows 显式平台 Project PATCH 组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A07。输入：PRJ-04-A06 可选 PATCH、PRJ-01-A06 内部写服务、Windows 显式平台组合；决策 `DEC-20260925-059`。
- Changed：`--platform`/`--platform-write` 在已有 Schema/License/游标信任源前置通过后，复用当前 Session、Project 授权、写仓库、Audit 挂载名称 PATCH。默认登录模式仍 404。
- Files：Windows 组合根、组合契约/临时 PostgreSQL 验证、决策/状态/版本记录。
- Migration：无。API：挂载冻结 `PATCH /api/v1/projects/{project_id}`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 393/393 PASS；默认模式 404、显式组合缺信任源失败关闭；PostgreSQL 18 临时库真实 Session/Project SQL 的 v1→v2 修改、陈旧版本 409、合成 License 拒绝 403、两次 Audit PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务已停止。
- Result：Windows 显式组合和隔离合成端到端 PASS；正式发行公钥/目标运行账户信任源未供给，PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 未验证；正式生产不得依赖测试信任源。
- Next：PRJ-04-A08 Project 单向归档 HTTP 的 If-Match/权限及幂等合同预检，按冻结 API 逐项接线。
