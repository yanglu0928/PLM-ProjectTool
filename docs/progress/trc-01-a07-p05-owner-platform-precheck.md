# TRC-01-A07-P05：撤销关系 Owner 与正式装配前置核查

日期：2026-10-02；Phase 2；结论：**PRECONDITION_BLOCKED（关系 Owner 与正式平台装配），项目转独立 Phase 2 Trace 任务**。本项只核查，不将 P04 可选 HTTP 验证视为正式交付。

## 依据和实际差异

- 冻结 API-02 的 `TRACE_LINK_REVOKE` 允许 ProjectManager、关系 Owner；现有 `TraceRevokeService` 和 Project 操作策略只接受当前 `PROJECT_MANAGER`。`trc_links.created_by` 是创建者审计事实，冻结合同没有规定其等于关系 Owner，不能把创建者自动提升为该权限。
- `TraceLinkRow` 没有独立 Owner 身份或受权证明；Document 是当前唯一注册的资源 Owner，但其版本/Scope Port 只能证明端点，不能证明谁拥有两端之间的关系。需要独立、可撤权的关系 Owner 规则/Port 与同事务测试；在此前非经理路径继续拒绝。
- `entrypoints/api.py` 只接受显式注入的 `trace_revoke_router`；Windows 正式组合 `production_login.py` 没有注入。默认/正式组合继续 404；P04 的显式测试路由不自动等于生产路由。
- `STATUS.md` 记录正式 License 公钥、目标账户密钥/可信时间、Server 2025 运行账户与恢复演练仍缺。不能用隔离 PG18 的合成 License/临时密钥代替正式信任源，也不为装配创建新 Secret 或迁移客户数据。

## 处理决定

维持 ProjectManager 内部命令及显式可选 HTTP 的已验边界，**不挂载正式平台**，不把 `created_by` 推断为关系 Owner，不修改冻结 API/Schema。关系 Owner 身份与授权粒度若需补充，须先登记 Trace 专项 Change Request，写明现有历史数据的处理、撤权语义、迁移/回滚和跨项目/失效端点验证。正式装配待真实目标账户信任材料与最小端到端验收；Server 2025/Debian 仍按实际环境单独判定。

本项无产品代码、数据库、API 或配置修改，无迁移；回滚仅撤销本核查记录，不影响已存在关系和路由。静态核查 API-02、`TraceRevokeService`、`TraceLinkRow`、应用工厂与正式组合；**未运行新的业务测试**，Gate 3、三平台、UAT 和可用程序包不因此通过。

Next：`TRC-01-A08-P01` 核查冻结 `TRACE_LINK_SUPERSEDE` 的替换原子性与前置；该内部 PM 路径可以独立于关系 Owner/正式装配推进，仍须先满足编码前检查，若存在冻结差异先登记 CR。
