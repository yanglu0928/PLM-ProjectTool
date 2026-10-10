# SOL-04-A09：Section GET Windows 显式只读/写组合

日期：2026-10-09。结果：`SOL_04_A09_SECTION_READ_WINDOWS_COMPOSITION_PASS`，限 Windows 11 合成信任源、隔离 PostgreSQL 18.6 的工厂/真实 ASGI 验证；正式目标服务账户/完整生产启动未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A09。
- 输入基线：冻结 API-04 `SOL_SECTION_GET`、A07 内部读 Owner、A08 可选 GET、现有 Windows Outline 读模式。
- 前置：Session/License/成员权限/同项目和指针复验、真实可选 HTTP 已通过。
- 模块/实体/API/权限：仅 Windows Solution 工厂与 production_login 显式读模式注入；不改实体、Schema/Migration、角色或冻结 API。Owner 复验所有当前 Project member。
- 验收：显式读工厂真实 Session/PG 200 和安全拒绝，缺依赖拒启动；默认/登录专用仍 404；只读模式 POST 404；后端全量。
- 风险：模式串线或目标账户信任材料缺失。仅 `include_secret_read` 分支创建读 Router，缺依赖 fail closed；正式账户独立验收。

## 实施与验证

`create_windows_section_read_router` 装配已验证的 Section 读 Owner/仓储、项目读授权，并由 `production_login` 显式只读与写模式共用；登录专用/默认应用不注入。Windows 11 一次性 PG18.6 工厂/真实 ASGI/Session 夹具验证项目成员 200、ETag/Trace、跨项目/暂停/Origin/License 拒绝、缺依赖启动失败，读应用 Section POST 404；原 PROJECT Reference 夹具回归通过。正式目标账户、公钥/Vault/HTTPS 的完整生产启动未运行。

后端全量 `3386 passed, 3 skipped, 5104 subtests passed`。兼容/升级/回滚：无新 Migration、依赖、前端或冻结 API 变化；撤下显式读 Router 注入即可关闭，Section 历史保留。下一项 Section LIST 内部 Owner/keyset 前置核查与独立游标签名设计；UI/浏览器另拆。Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
