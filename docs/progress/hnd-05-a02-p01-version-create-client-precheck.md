# HND-05-A02-P01：交接分析 DRAFT 版本安全客户端编码前检查

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / UI_AND_PACKAGED_PENDING`。

|检查项|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A02-P01`；仅将已冻结的 Handover Version POST 接入私有 Session 传输和严格响应核验，不在此项生成或批准问题。|
|输入基线|Gate 2 冻结 HND-01 `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions`；CR-EXEC-002；`CAP-02-A05-P03-P02-A03` 当前批准 GLOBAL Capability 合成包内通过；`EVD-05-A03-P03` PROJECT Evidence 合成包内通过。|
|前置与权限|分析需 ACTIVE、同固定文档集、当前批准 CapabilityBaselineVersion、至少一项有同项目 ELIGIBLE Evidence 的真实来源问题；仅 `HND_VERSION_CREATE` 项目角色，CSRF/Origin/If-Match/幂等 Key，由服务端最终重验。前端不授予额外角色。|
|API/Schema/迁移|不改 API、Schema、权限、License 或冻结合同；SessionClient 新增已存在路由的调用，严格 2 MiB 上限，错误与不确定结果保留原 Key/ETag/正文。|
|验收|合法/畸形输入与回执、权限预筛、错项目、版本冲突、同 Key 重试、不确定结果及浏览器原生 fetch receiver 的定向测试；全量前端回归、typecheck/build。实际 Edge/PG 归后续页面与包内 WBS。|
|已知后续障碍|HandoverAnalysis 首次创建只持久化 `source_set_ref` 哈希，首个版本之前的固定文档引用无法从分析读 API 取回；页面需让用户重新选择并由服务端验证精确同集，或另立可追溯 CR 增加来源持久化/读路径。不得从哈希猜测或伪造来源。AI 建议不得自动成正式问题。|

编码前结论：客户端工作前置满足；版本界面与客户确认不在本 WBS 预先放行。回滚为移除未接入界面的客户端与 Session 路由，不删已存在的分析/证据/能力历史。

实施结果：`SessionClient` 新增已冻结版本 POST 的私有 CSRF/Origin 同源请求、2 MiB 上限、If-Match 与幂等 Key；`HandoverVersionCreateClient` 对来源、能力版本、1～500 项问题、证据、待确认项必填提示和回执作严格校验。网络超时、非 JSON 或不一致的 201 回执进入“不确定”安全态，调用者须保留同一正文/Key/ETag 核对历史；不创建正式批准或客户确认。定向4、前端全量1966项、typecheck/build退出0。当前仅客户端合同通过，尚无页面、Edge/PG 或包内 Handover Version 创建证明。Next：`HND-05-A02-P02` 重新核查首版本原分析固定来源恢复与可用的卡片式用户输入，不能从 `source_set_ref` 哈希伪造文档列表。
