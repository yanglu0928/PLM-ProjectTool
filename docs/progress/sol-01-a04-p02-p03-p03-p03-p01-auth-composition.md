# SOL-01-A04-P02-P03-P03-P03-P01：人工确认真实 Auth 数据库组合

日期：2026-10-08；结果：`AUTH_PG_PASS`，P03-P03-P03 完整 Document/Evidence 组合未完成。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P02-P03-P03-P03-P01
输入基线：冻结 DM-05/API-04、CR-SOL-006、0142 与撤销/读取内部命令
前置：确认、读取、撤销内部 Port 及隔离 PG 验证通过
涉及模块/实体：Auth Session/User/Credential，Solution 确认/撤销/Proof
API/权限：无公开 API；当前 DeploymentAdmin Session/CSRF/License
验收：真实 PG Session/角色/CSRF 查询、确认→读取→撤销、错误 CSRF/撤销会话拒绝
风险：身份行由隔离夹具合成，未走真实登录；License 和来源 Proof 仍为合成 Port
```

独立 Windows 11 / PostgreSQL 18.6 临时实例复用既有迁移/确认/撤销回归，然后在临时库创建合成管理员凭据与 Session。内部确认和撤销使用真实 `SqlAlchemyLicenseImportAccess`，读取使用真实 `SqlAlchemyDeploymentReadAccess`：正确 CSRF 可以确认/撤销，错误 CSRF 不能写，确认在有效 Session 下可读，撤销后不可读，Session 标记撤销后确认/撤销和读取均拒绝。脚本退出0并清理本轮数据库和文件目录。

本项只增强 Auth 组合证据；Document/Evidence 来源仍由合成 Port 返回，没有真实文件字节、Evidence 节点、正式登录、公开 HTTP 或用户人工核查，不能将其描述为完整人工确认可用。下一项必须以实际 Document/Evidence PG+物理文件适配替换合成来源，并对篡改、跨范围和撤销重验。TraceLink：CR-SOL-006 → DEC-20261008-1108 → Auth PG 脚本 → 后续真实来源组合。
