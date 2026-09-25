# PRJ-04-A10-P01：成员创建幂等前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A10-P01。来源：冻结 API-01/02、CR-API-001、PRJ-02-A02；差异 CR-PRJ-002；决策 DEC-20260925-067。
- Changed：内部成员创建新增同事务持久幂等；首次 201 MemberView 的类型化不可变快照由 Project 模块持有，通用收据只存引用。重放验证当前 Session/CSRF、License、ProjectManager，允许已归档项目重放既有成功，但不允许在归档后新建。旧非幂等内部调用保持兼容。
- Migration：`20260925_0016`；空库/已有数据升级仅建表，空表可降级，非空拒绝降级。升级前备份数据库；不补造历史创建结果。
- Tests：Windows 11/Python 3.13 后端 410/410 PASS；PostgreSQL 18 临时库空表 up/down、已有数据升级、同 Key 并发一次写入/审计、异载荷冲突、审计失败回滚、创建后资料变化及归档原样重放、快照不可变与非空降级拒绝 PASS；开发 wheel 构建 PASS。临时库已删除，服务停止。
- Result：内部服务幂等前置 PASS；公开成员创建 HTTP、Windows 平台组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；生产升级需先备份并运行 Migration。
- Next：PRJ-04-A10-P02 可选成员创建 HTTP，按冻结合同做真实 Session/CSRF/License/权限/幂等端到端。
