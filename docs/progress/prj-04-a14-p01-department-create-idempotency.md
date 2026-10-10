# PRJ-04-A14-P01：Department 创建持久幂等前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A14-P01。来源：冻结 API-01/02、PRJ-03-A02 内部创建、CR-API-001；差异 CR-PRJ-004；决策 DEC-20260925-079。
- Changed：内部部门创建新增同事务持久幂等。Project-owned `prj_department_create_results` 保存首次 201 DepartmentView 的不可变类型化快照，通用收据只存引用；重放重新检查当前 Session/CSRF、License、ProjectManager，不重复创建或 Audit。项目归档后只允许重放既有成功，不允许新写；旧非幂等内部命令保持兼容。
- Migration：`20260925_0018`；空库/已有数据升级只建表，空表可降级，非空拒绝降级。升级前备份数据库；不补造历史创建结果。
- Tests：Windows 11/Python 3.13 后端 431/431 PASS；PostgreSQL 18 临时库空表 up/down、已有数据升级、ORM drift=0、同 Key 并发仅一次部门/Audit、异载荷冲突、审计失败回滚、名称/编码/状态变化和归档后原结果重放、快照不可变与非空降级拒绝 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：内部创建命令幂等前置 PASS；公开 HTTP、Windows 平台组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；生产升级须先备份并运行 Migration。
- Next：PRJ-04-A14-P02 可选创建 HTTP，按冻结合同验证 Idempotency-Key、权限和许可。
