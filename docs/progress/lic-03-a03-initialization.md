# LIC-03-A03：一次性受控可信时间初态初始化

- 日期：2026-09-24；结果：PASS（内部命令，用户选择的方案 A）；依据：Gate 2、ADR-006、DM-02、CR-EXEC-001、DEC-20260924-096。
- Changed：有效 DeploymentAdmin Session/CSRF 才能显式创建部署级可信时间空状态；已有状态或只有事件历史时拒绝，重复执行不重置。数据库事务锁与单例约束防止并发双建；初始化和 Audit 同事务，审计失败回滚。日常 TrustedTimeStatePort 保持不自动补建。
- Files：`trusted_time_initialization.py`、`trusted_time_initialization_repository.py`、单元测试、临时 PostgreSQL 验证脚本和追溯文档。Migration：无。API：无公开路由。Permission：Auth 拥有的 DeploymentAdmin Session+CSRF 适配器。
- Tests：Windows 11/Python 3.13 后端 188/188 PASS；服务单元覆盖率 98%；PostgreSQL 18.6 一次性库首次初始化、错误 CSRF 拒绝、审计回滚、两请求并发不重置 PASS；后端 wheel 构建 PASS；项目 Skill 验证 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：本项只创建无成功时间的空状态，不产生或接入生产 HMAC 密钥、公钥或选定 MAC；不得把空状态视为可用 License。尚未挂公开 HTTP、安装流程及生产 SecretKeyProvider；生产密钥保护/恢复按 CR-EXEC-001 留待 PLT-02/Release。测试未覆盖完整断网安装/UAT，Gate 3/Release 未通过。
- Next：`PLT-02-A01 SecretRecord ORM/Migration` 编码前检查，推进冻结的加密 Secret Store 数据层；生产密钥来源仍单列 Release 安全设计任务。
