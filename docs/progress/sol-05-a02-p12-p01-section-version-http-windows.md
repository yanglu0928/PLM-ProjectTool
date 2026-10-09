# SOL-05-A02-P12-P01：SectionVersion CREATE 可选 HTTP 与 Windows 装配

日期：2026-10-09。结果：`SECTION_VERSION_CREATE_HTTP_WINDOWS_ASGI_PG_PASS`；仅合同/组合/一次性 ASGI+PG，真实 Edge 浏览器与正式发行仍待 P12-P02。

## 编码前检查

Phase 2 Platform Core；WBS `SOL-05-A02-P12` 的 P01 可验收切片。输入冻结 API-04 的 `SOL_SECTION_VERSION_CREATE` 路径与动作、CR-SOL-003/P07～P11；内部 Owner 和 0160 Guard 已满足。单一问题是提供严格、可选的 POST HTTP 边界，并仅在 Windows 显式 `--platform-write` 组合挂载。无 Schema、权限、技术栈或冻结 `/api/v1` Breaking Change。验收为请求/成功/错误合同、默认 404、缺安全依赖失败关闭、真实 Session/Document/Requirement/Evidence/PG 的 201/重放/负例。风险为默认暴露、来源证明跳过、客户正文进入日志或合成信任误作正式材料。

## 实施与验证

新增 Solution `section_version_create` HTTP Router，严格 JSON/UTF-8/重复键/上限/未知字段校验；标题、DocumentVersion/Artifact XOR、固定 Requirement/Evidence 与声明先通过有界输入合同。响应保留首次 DRAFT 的版本/正文引用、固定引用、声明/计数、指纹、创建人/时间、空 Review，201 带 Location/no-store/Trace；内部错误映射不泄漏回溯。默认 `create_app()` 不挂路由。Windows Solution 组合工厂把真实 Document 物理证明、Requirement 当前批准证明、Evidence 当前资格、Project/Auth/License/收据/Audit 接到 P11 Owner，仅在 `production_login` 的显式写模式装配；缺任一依赖启动失败。

合同测试 4 通过/17 子测试；Windows 11 一次性 ASGI+PG 脚本 `validation/sol-05-a02-p12-section-version-http-pg/verify.py` 退出0：经理 201/同键同响应、同键不同正文冲突、实施成员升版、跨项目/CSRF/Origin/缺 Key/Artifact/License 拒绝、文件篡改时新请求失败而原键重放、SQL 版本/首响应/Audit 数量核对；同时重跑 P11 来源 Owner 及上游真实 Document/Evidence 验证。后端全量 3536 通过、3 跳过、5531 子测试通过。测试使用合成批准 Requirement/Review、合成 License 与一次性 PG，不代表客户确认或正式信任。真实浏览器/Uvicorn、Windows Server2025、目标服务账户和生产公钥尚未验证，不标完整 P12 PASS。

兼容/回滚：无 Migration/旧数据/API Breaking Change/依赖变化；禁用显式写组合或移除可选路由可回滚入口，已提交业务历史/收据/Audit 不删除。P12-P02 将做真实 Edge+网络+PG 与装配故障验证；后续 GET/LIST/VALIDATE/Review/Trace/Spec、性能、Gate3/UAT/发行另验，Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-003 → P11 → DEC-1178 → 本 P12-P01 → P12-P02 Edge/网络 → Gate3。
