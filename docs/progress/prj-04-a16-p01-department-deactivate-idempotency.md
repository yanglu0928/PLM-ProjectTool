# PRJ-04-A16-P01：Department 停用持久幂等与快照

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A16-P01。来源：冻结 API-01/02、PRJ-03-A04、CR-PRJ-005；决策 DEC-20260925-084。
- Changed：内部停用新增独立幂等入口，先复核当前 Session/CSRF、License、ProjectManager 与 Department 所属；同 Key 同规范请求返回首次 DepartmentView，不重复停用/审计，异载荷冲突。新增 Project-owned、仅追加结果快照和 `PROJECT_DEPARTMENT_IN_USE` 409 错误码，旧内部命令不变。
- Files：Project Application/Authorization/Repository/ORM、Migration `20260925_0019`、Platform 错误码、单元测试和 PostgreSQL 验证脚本。API：无新公开路由或 Breaking Change。
- Compatibility/Upgrade：目标库升级前备份并执行至 head；空快照表允许降至 `0018`，非空拒绝普通降级，无新增外部依赖。
- Tests：Windows 11/Python 3.13 后端 438/438 PASS；PostgreSQL 18 临时库空表 up/down、已有数据升级、ORM 差异、顺序/并发同 Key 单写、成员在用拒绝、权限/License 重放复核、审计失败回滚、快照不可变与非空降级保护 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：内部幂等前置 PASS；公开 HTTP、Windows 平台组合、正式信任源、Gate 3 与最终程序包未完成。
- Known Issues：Server 2025/HTTPS 与 Debian 13 本项未验证；合成 License 不代表正式发行验收。
- Next：PRJ-04-A16-P02 新增可选 Department 停用 HTTP。
