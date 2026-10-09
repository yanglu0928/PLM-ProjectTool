# SOL-01-A16-P06-P01：Reference Eligibility 前端安全请求桥

日期：2026-10-09。结果：`SOL_01_A16_P06_P01_REFERENCE_ELIGIBILITY_CLIENT_PASS`；仅客户端，页面/真实浏览器尚未接入。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / SOL-01-A16-P06-P01。输入：冻结 API-04、CR-SOL-014、A16-P04 双 Scope HTTP、A16-P05 Windows 显式组合；前置满足。
- 单一问题：为人工资格决定提供可信前端请求与结果解析，不在本任务实现页面或代替真人确认。涉及 Auth Session 私有写桥和 Solution API 客户端；实体为当前 Reference 根/不可变资格结果；权限为 PROJECT ProjectManager 或 GLOBAL DeploymentAdmin。
- 验收：客户端只接受当前 GET 的 Scope/身份/强 ETag，校验状态转换、理由/操作号；POST 不重试，结果须精确匹配原版本、目标状态、理由、递增 ETag；错误/网络不确定保持区别；详情读取接受 Schema 合法的 2000 字理由。
- 风险：P05 成功回执为历史快照，不代表现时资格；页面必须重新 GET。现有详情客户端上限 1000 与后端 2000 不一致，已在 CR-SOL-014 实施前登记，选定前向兼容修正。

## Changed / Files / Migration / API

- `SessionClient` 增加私有 CSRF 管理下的 `:set-eligibility` 单次写桥，复用 Revise 的锁/幂等安全边界；无响应后自动重试。
- 新增 `referenceEligibilityClient.ts`：双 Scope、Role、合法转换、理由 NFC/控制字符/2000 字、强 ETag/幂等校验；首次结果严格投影，未知结果不可当成功。
- PROJECT/GLOBAL 详情读取客户端对齐已发布 Schema 的 2000 字理由，2001 字继续拒绝；配套新合同测试。
- 文件：`apps/frontend/src/modules/auth/api/sessionClient.ts`、`apps/frontend/src/modules/solution/api/{referenceEligibilityClient.ts,referenceEligibilityClient.spec.ts,referenceReadClient.ts,referenceReadClient.spec.ts,globalReferenceReadClient.ts,globalReferenceReadClient.spec.ts}`、CR/状态/版本说明。
- Migration：无。API：既有冻结路径/字段不变；仅新增前端客户端，不改变服务端合同。

## Tests / Result

- 定向 3 文件/14 测试：PROJECT/GLOBAL 路径、CSRF/强锁/幂等、Role/理由/终态负例、网络不确定/错误结果、2000/2001 字读取边界通过。
- 前端全量 120 文件/1703 测试通过；typecheck 与 build 通过。构建报告现有主 chunk 大于 500 kB 的性能提醒，未作为本任务新 Gate 通过证据。

## Known Issues / Next

无 DB/后端/依赖/Secret/客户数据外发。回滚前端客户端代码即可，但撤销 2000 字兼容修复会重新暴露合法理由读取失败。P06-P02 接 PROJECT/GLOBAL 详情人工理由/二次确认/提交后当前态重读；P06-P03 做 Win11 Edge/隔离 PG 浏览器验收。真人判断、正式目标账户/HTTPS/License、Server2025、20 并发、Gate3/UAT/发行未验；Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-014 → A16-P01～P05 → 本 P06-P01 → P06-P02/P03 → Gate3。
