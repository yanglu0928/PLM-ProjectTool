# SOL-01-A04-P08-P03-P03：GLOBAL Reference 人工确认可注入 HTTP 合同

日期：2026-10-09；结果：`GLOBAL_REFERENCE_ATTESTATION_HTTP_CONTRACT_PASS`，仅可注入 Router/合同测试通过，默认及 Windows 生产组合均未挂载。实际人工核查、真实 PG/HTTP 与目标发行入口不在本项验收范围。

编码前检查：Phase 2；输入冻结 API-01/API-04、CR-SOL-009 与 P08-P02 增量合同；前置来源 Proof、写时指纹栅栏、Preview/Confirm/Revoke 内部 Owner 已完成。只涉及 Solution HTTP 边界与通用错误登记，无 Schema/依赖变化。实体为 GLOBAL 来源预览、确认、撤回；API 为新增 Preview/Confirm/Revoke POST；权限为可信 Host/Origin、当前 Session/CSRF、服务层 DeploymentAdmin/License。验收要求严格 JSON、固定来源、幂等、错误分类、最小投影、默认关闭；风险是合成 HTTP 验证不能代替实际管理员逐项打开原文并明确声明。

实现 `create_reference_deidentification_router`：Preview 只读；Confirm 强制 64 位小写预览指纹、精确人工声明、UTC 过期时间与 Idempotency-Key，并由内部服务在写入前复验现时来源；Revoke 强制受限原因和幂等。路由统一执行 Session/CSRF/可信 Origin、拒绝 query/未知或重复 JSON 键/超 128 KiB 请求，响应仅返回固定身份与时间、Trace、`no-store`。内部管理员和 License 仍由 Owner 校验。`SOURCE_SNAPSHOT_CHANGED` 登记为 409；默认应用和 GLOBAL Reference Create 保持 404，尚无生产组合挂载。

验证：定向合同 `3 passed, 10 subtests`，覆盖三项成功投影、默认 404、无 Session/非法 Origin/CSRF、严格请求、无幂等 Key、来源越权/License/不可用与指纹漂移 409；全量后端 `3330 passed, 3 skipped, 4919 subtests passed`。首轮发现 HTTP 边界的本地字段错误被宽泛异常误映射 503，调整校验位置后复验 422；非生产数据，无迁移。后续仍需真实 PG/HTTP、Windows 显式安全组合、前端逐项查看/勾选、Edge 和实际人类业务确认；正式 License/目标账户、Server 2025、20 并发/Gate 3/发行未验，Debian 13 依用户指令跳过。

兼容/回滚：仅新可选 Router 和错误码，既有 API/Schema/依赖不变；可移除可选注入使三入口继续 404，无数据回滚。TraceLink：CR-SOL-009 → P08-P02 合同 → P03-P01/P02 内部服务 → P03-P03 HTTP/合同/全量 → 后续真实 PG/Windows/UI。
