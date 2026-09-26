# PLT-02-A06：Secret 停用命令

- 日期：2026-09-25；结果：PASS（仅内部服务）；依据：冻结 DM-02/API-02、CR-EXEC-001、DEC-20260925-004。
- Changed：按内部命令在 DeploymentAdmin Session+CSRF 与 License Guard 后再次确认管理员；用期望 Record lock_version 和行锁保护状态转移。停用把当前密文版本退役、Record 置 DISABLED 并清除 current_version_ref，Audit 同事务；重复/陈旧请求返回版本冲突。受控读取不再取得该 Secret。原拟 A06 的公开管理 API 拆为 A07，待身份/许可生产装配、If-Match 与幂等支撑完成后接线，不能因内部服务通过而提前开放。
- Files：`secret_write.py`、`secret_write_repository.py`、单元测试、`validation/plt-02-a06-secret-disable/verify.py`、决策/状态/版本说明。Migration：无。API：无公开路由。Permission：DeploymentAdmin Session+CSRF+License；期望版本与行锁。
- Tests：Windows 11/Python 3.13 后端 207/207 PASS；写服务目标覆盖率 97%；PostgreSQL 18.6 临时库停用/历史/读拒绝/重复拒绝/Audit PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：本项集成使用合成 Access、License Guard 与 Key Provider；生产信任来源和公开 API/Idempotency 尚未接线。停用后的恢复必须走新受控版本命令设计，不能用数据库手工复活历史；不能配置真实 Secret。
- Next：`PLT-02-A07 Secret 管理 API 与生产装配前置审查`，同时推进生产 Key Provider 安全设计与实现。
