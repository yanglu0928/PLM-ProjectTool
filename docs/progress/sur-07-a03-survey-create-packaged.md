# SUR-07-A03：调研定义创建 Windows 11 非发行包验收

日期：2026-10-25；状态：`PRECHECK_PASS / PACKAGED_EDGE_PG_PENDING`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A03`；仅证明调研定义 UI Create 在固定包内真实运行，不添加版本问题或冻结 API 变更。|
|输入基线|`SUR-07-A01/A02` 已通过前端全量2022/typecheck/build，干净源提交 `10c8b72cc64a194704be2f00c8b738958a64cd46` 已推送。|
|包源|后端自 `98df564e` 至当前无文件差异，可复用 P06 已验证 wheel SHA `b2053a4a4b3e1648293514cbfd59f73786b227e3a2abf64ce4d11a7e99d10d4e`；固定 parent SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。候选只替换当前前端 dist，必须绑定此干净提交。|
|验收|独立清洁解包/逐件哈希；复用包内合成项目→交接批准链后，在真实 Edge/HTTPS/隔离 PG 中从项目调研列表创建定义，验证唯一 Survey/Audit/收据、同号重放、只读角色/跨项目/License 拒绝、临时进程/Vault/布局清理。|
|安全|仅合成账户、TLS 与 License；不上传 ZIP/Secret/客户资料，不把调研定义当访谈事实，`release_eligible=false`、`legal_clearance=false`。|
|回滚/已知缺口|无 Schema/API/License 改动；失败保留候选与证据，先修复后重建/重测。正式公钥、服务账户/CA/法律、离线升级、调研版本/实际记录、UAT/Gate/正式多平台仍未验。|

前置核查通过。实际包内结果待独立验收，不预写 PASS。
