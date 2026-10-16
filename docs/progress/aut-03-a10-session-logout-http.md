# AUT-03-A10：Session 注销 HTTP

- 日期：2026-09-25；结果：PASS（Windows 11 合成环境，冻结注销合同；Gate 3/UAT 未通过）。
- 当前Phase：Phase 2 Platform Core；当前WBS：AUT-03-A10。
- 输入基线：Gate 2 冻结 API-02 `AUTH_LOGOUT`、AUT-02 Session 撤销、API-RUNTIME-01/CR-API-001 通用持久幂等；前置 AUT-03-A07-P03～A09 PASS。
- 涉及模块：Auth API/Application/Infrastructure、Platform 幂等收据、Audit；实体：Session、`plt_idempotency_receipts`、AuditEvent；API：显式生产组合根挂载冻结 `POST /api/v1/auth/logout`，普通默认应用仍 404；权限：首次要求有效 Session/CSRF/Origin/Host，同 Key 重试仅核对原 Session 摘要、原 CSRF 与已完成收据，不恢复任何业务权限。
- 验收标准：唯一严格 Cookie、CSRF 和 16～128 可打印 ASCII 的 `Idempotency-Key`，空请求体；首次在同一事务内预留收据、撤销 Session、写 Audit、完成收据；成功 200 revoked 并清除 Cookie；同 Session/同 Key 原语义重放，错误 CSRF/Origin 拒绝，不同 Session 同 Key 409，不同 Key 对已撤销 Session 401；并发仅一条注销审计/收据，旧 Cookie 不可查询；审计失败整体回滚。
- 风险：历史注销重试会在准确匹配时返回 200，但绝不使旧 Session 可再次访问 GET 或业务 API；Session 和收据 Retention 必须协调，在现有未启用自动删除阶段保持记录。重复请求的 TraceId 随请求更新，不复写原业务结果。

Changed：SessionService 增加显式 `logout`，将通用幂等收据与已有撤销/Audit 纳入同一 UoW；已撤销重试在收据并发等待后重新读取 Session，核对 `LOGOUT` 原因及结果引用。新增严格 HTTP 边界与 Cookie 清除，Windows 生产组合根显式挂载。保留原内部 `revoke` 方法和默认应用无公开 Auth 路由行为。

Files：Auth Session Service/Repository/API、Platform Key 校验复用、应用组合根、单元/合同测试、一次性 PostgreSQL 验证增强及决策/进度/版本/状态。Migration：无，依赖前项 `20260925_0015`；升级须先到该 head。API：冻结路径按合同实现，无 Breaking Change。

Tests：Windows 11/Python 3.13 后端 329/329 PASS；一次性 PostgreSQL 18.6 + Windows Vault 登录/GET/续期/注销，同 Key 串行及并发重放 200、不同 Session 同 Key 409、旧 Cookie GET 401、唯一收据/审计、Cookie 清除 PASS；单元验证审计失败时 Session 与收据一起回滚；合成库/角色/凭据已清理，PostgreSQL 已停止；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：管理员/License/Secret API、If-Match 公开接线、生产 Key Provider/HTTPS 服务、跨平台发行和最终程序包尚未完成；POC-03 质量失败仍阻断 Gate 3/UAT。

Next：复核 `PLT-02-A07` 尚缺的生产 License/Secret Key Provider 与 If-Match/权限装配，优先推进可真实验收的下一项，不用合成依赖开放管理接口。
