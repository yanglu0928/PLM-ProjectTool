# PLT-02-A05：Secret 管理写入与轮换命令

- 日期：2026-09-25；结果：PASS（仅内部服务）；依据：冻结 DM-02/API-02、CR-EXEC-001、CR-PLT-002、DEC-20260925-003。
- Changed：Platform 内部创建/轮换命令先检查 DeploymentAdmin Session+CSRF，再检查 License Guard；写事务再次验证管理员。创建只返回 SecretRef；轮换须提供期望版本号，锁定当前活动记录后写新密文版本，旧版退役，新版激活，记录指向新版；审计与所有写入同事务。输入可变明文即使拒绝也在返回前清零；异常映射为固定错误码，不回显值/密文。
- Files：`secret_write.py`、`secret_write_repository.py`、Secret 加密草稿移至应用层、单元测试、`validation/plt-02-a05-secret-write/verify.py`、决策/状态/版本说明。Migration：无。API：无公开路由。Permission：DeploymentAdmin Session+CSRF+License，数据库行锁与期望版本。
- Tests：Windows 11/Python 3.13 后端 205/205 PASS；写服务目标覆盖率 96%；PostgreSQL 18.6 临时库创建/轮换、读回新值、密文存储、历史、双线程竞争、无权/CSRF/许可/陈旧版本拒绝及审计失败回滚 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：集成只用合成 Key Provider 和合成 License Guard，生产密钥与 License 完整装配未完成；公开 HTTP/Idempotency/If-Match 接线及停用命令未完成。Guard 与写事务分开，许可在检查后变化的窗口尚待正式集成安全审查；不能配置真实 Secret。
- Next：`PLT-02-A06 Secret 停用命令与管理 API 接线`，生产 Key Provider、备份恢复和三平台发行继续单列。
