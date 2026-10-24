# PRJ-04-A12-P01：成员状态命令持久幂等前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A12-P01。来源：冻结 API-01/02、PRJ-02-A04 内部状态机、CR-API-001；差异 CR-PRJ-003；决策 DEC-20260925-072。
- Changed：SUSPEND/RESUME/REMOVE 内部命令新增同事务持久幂等。Project-owned `prj_member_state_results` 保存每次首次 200 MemberView 的不可变类型化快照，通用收据只存引用；重放重新检查当前 Session/CSRF、License、ProjectManager 和目标归属，不重复状态转移或 Audit。项目归档后只允许重放既有成功，不允许新写；旧非幂等内部命令保持兼容。
- Migration：`20260925_0017`；空库/已有数据升级只建表，空表可降级，非空拒绝降级。升级前备份数据库；不补造历史状态事件。
- Tests：Windows 11/Python 3.13 后端 418/418 PASS；PostgreSQL 18 临时库空表 up/down、已有数据升级、ORM drift=0、三个操作各自同 Key 并发仅一状态/Audit、异载荷冲突、审计失败回滚、后续状态及显示名称变化和归档后原结果重放、快照不可变与非空降级拒绝 PASS；开发 wheel PASS。临时库已删除，服务停止。
- Result：内部状态命令幂等前置 PASS；公开 HTTP、Windows 平台组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；生产升级须先备份并运行 Migration。
- Next：PRJ-04-A12-P02 可选状态命令 HTTP，按冻结合同验证强 If-Match、Idempotency-Key、权限和许可。
