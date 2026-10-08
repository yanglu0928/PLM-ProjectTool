# CR-PRT-004：Prototype Version 校验写操作的 Auth 接线修复

日期：2026-10-08。状态：依 CR-EXEC-001 持续授权实施；不改写 Gate 2 原冻结提交。

PRT-01-A10-A07 真实 Windows 11 Edge 流程中，Version CREATE 经 CR-PRT-003 修复后返回 201，但 `PRT_VERSION_VALIDATE` 返回 503。原始异常为只读 `SqlAlchemyProjectReadAccess.authenticated_user()` 不接受 `csrf_token`。服务把只读 GET 和需 CSRF 的校验写入共用一个 Auth 适配器；模拟测试的宽松假对象未发现该生产接线错误。

决策：Version Read/Validation 服务明确区分只读会话适配器与 CSRF 写会话适配器；GET 保留原读证明，VALIDATE 使用已有 `SqlAlchemyProjectWriteAccess`。不得绕过 CSRF、放宽会话证明或改变冻结 API、权限与幂等语义。增加严格区分两个接口的单元回归，并以真实 Edge → FastAPI → PostgreSQL 验证。

无 Schema、依赖、外发或数据迁移。应用回滚可恢复旧接线，但会重新阻断校验，因此发行回滚须同步回退对应 UI 功能并声明限制。Windows Server 2025 和 Debian 13 不由本次 Windows 11 验证推定通过。结果记入 STATUS/版本说明并同步 GitHub。
