# PRJ-04-A05：Windows 显式平台 Project 创建组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A05。输入：冻结 `PROJECT_CREATE`、PRJ-04-A03 同事务收据、PRJ-04-A04 可选 HTTP、Windows 显式平台 Schema/License/Session 组合；决策 `DEC-20260925-057`。
- Changed：仅在 `--platform`/`--platform-write` 模式的既有信任源前置通过后，以现行 SessionService、LicenseRuntimeGuard、Auth 管理员/负责人资格、Project SQL 创建、Audit 和通用收据挂载创建 Router。默认登录模式仍 404；不新增配置中的权限或 Key 来源。
- Files：Windows 组合根、组合契约/临时 PostgreSQL HTTP 验证、决策/状态/版本记录。
- Migration：无；目标库需已有 `0015`。API：只挂载冻结 `POST /api/v1/projects`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 390/390 PASS；默认模式 404、显式平台入口安全门；PostgreSQL 18 临时库真实 Session/Project SQL 同 Key 两次 201 仅一个 Project/Audit、非管理员 404、合成 License 拒绝 403 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：Windows 显式组合和隔离合成端到端 PASS；正式发行公钥/目标运行账户信任源未供给，PRJ-04 整体、Gate 3 与可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 未验证；正式客户项目创建不得依赖测试信任源。
- Next：PRJ-04-A06 Project 元数据 PATCH 的强 If-Match 与权限 HTTP；其他 Project/Member/Department 端点继续逐项接线。
