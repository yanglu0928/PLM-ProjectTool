# AUT-01-A02 User/Credential 内部命令与规范化验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结内容 `64cdf09` 的 DM-02/API-02、A01 已验收 Schema 与 `DEC-20260924-076`。
- 实现：Auth 内部 CreateUser 命令、Unicode trim/NFC/casefold 规范化、用户名冲突处理、必需权限/Hash Port、初始凭据版本 1、真实 AuditService 同事务追加及密码缓冲区尽力清理。无公开路由、无登录/重置/停用命令。
- 验收：Windows 11/Python 3.13 后端 107/107；PostgreSQL 18.6 临时独立库规范化创建、Unicode/大小写重名、拒权、Audit 故障导致 User/Credential 整体回滚、密码缓冲区清理与不落明文 PASS。验证入口：`validation/aut-01-a02-user-command/verify.py`。
- Migration/API：无新增；沿用 `20260924_0006`。无升级步骤，安装更新 wheel 即可。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：验收哈希器是不可用于登录的 `TEST_ONLY` 测试替身；没有生产 Hash/Verifier、真实 Session/License/DeploymentAdmin 授权、公开 API 或持久幂等。Python 内存清零仅尽力缩短作用域，不能保证移除所有副本。下一项为 `AUT-01-A03 生产密码哈希与凭据校验`；Gate 3/UAT 未通过。
