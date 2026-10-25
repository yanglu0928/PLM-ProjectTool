# SOL-05-A02-P12-P02 SectionVersion CREATE Edge/网络验收

日期：2026-10-09。结果：`SOL_05_A02_P12_P02_EDGE_NETWORK_PG_PASS`，限 Windows 11 隔离合成环境。

按 CR-SOL-003/DEC-1178 的 P12-P02 计划，复用 P11 的一次性 PostgreSQL 18.6、真实 Session/Project/Document/Evidence 适配器和合成一致的 APPROVED Requirement/Review。启动独立 Uvicorn loopback 服务；真实 headless Edge 经 CDP 设置合成会话 Cookie，在同源页面中调用冻结 POST。观察 201 DRAFT/Location、同键重放同一首响应、不同正文 409、跨项目 404、CSRF 403、缺 Key 422、Artifact 无 Owner 503。服务停止后实库核对章节版本、首响应、持久收据、Audit 各 6 条（P11 已有 5 条，Edge 仅新增 1 条）；一次性数据库/角色/Vault 与 Edge 临时 Profile 由自有夹具清理。脚本 `validation/sol-05-a02-p12-section-version-edge-pg/serve.py` 退出0。

本项只增加可重跑验证资产，不改生产代码、Schema、权限或依赖。P12-P01 已覆盖可选工厂缺依赖失败关闭及 ASGI 来源篡改/License/Origin；本项不把合成来源写作客户确认，不证明正式 HTTPS、真实目标服务账户/公钥、Windows Server 2025、UI 页面、性能或 Gate 3。旧 0138 完整脚本仍未恢复 PASS，独立处理。Debian 13 实机依用户指令跳过。

兼容/回滚：无产品变化；可移除验证资产，不清除正式历史。TraceLink：Gate2 API-04 → CR-SOL-003 → P11 → P12-P01 → 本 P12-P02 → 后续 SectionVersion 读取/Review/Trace/Spec 与 Gate3。
