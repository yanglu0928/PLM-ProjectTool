# HND-05-A02：交接分析版本用户入口前置核查

日期：2026-10-24；结果：`PRECONDITION_BLOCKED / PIVOT_CAPABILITY_AND_EVIDENCE`。此项为静态前置核查，未编写版本创建界面或提交业务版本。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `HND-05-A02`：分析已能创建，核查下一步固定版本/问题卡片的可用用户写入口|
|输入基线|Gate 2 冻结 HND-01 创建合同、CR-EXEC-002、`HND-05-A01` 源码与 `PKG-PILOT-01-A04-P06` 包内创建切片 PASS；遵守用户要求的卡片式待办、原文定位、填写提示及 AI 建议不得自动成事实|
|前置任务|已有 Handover Version POST/读页；创建需 1～500 个真实问题项、原分析固定文档集、当前已批准的全局 CapabilityBaselineVersion、每个非缺源问题的同项目/同固定文档 Evidence，AI 任务引用仅可为成功的 GAP_ANALYSIS。当前干净包内仅创建了 DocumentVersion/HandoverAnalysis，未形成已批准能力基线、Evidence 与有来源的问题项。|
|涉及模块/实体/API|HandoverAnalysisVersion、Item、Evidence、CapabilityBaselineVersion、AITask；冻结 `POST /api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions` 需 If-Match、CSRF/Origin/幂等，既有读页仅展示版本/卡片/定位。无新 API/Schema 申请。|
|权限|版本创建仅原有授权角色；全局能力基线的审批不能由项目负责人或 AI 输出代替，Evidence 必须按项目和文档固定版本重证；客户确认及正式评审仍由独立权限链负责。|
|拟定验收|先取得可在 UI 查阅并形成当前已批准能力基线的正式路径，再把 AI 建议、原文位置与受控 Evidence/问题草稿做逐项候选映射及人工确认；创建至少一个真实来源的 DRAFT 版本，严格回执、同号重试、负例、Edge/PG；不把候选当批准版本。|
|风险/阻塞|当前前端无 Capability 模块入口；现有 AI 建议卡片提供来源位置链接，但并非 Handover `evidence_refs`/`required_input_spec` 的可提交证明。直接增加 UUID/JSON 大表单或 `source_missing=true` 假问题虽可绕过前端，却会制造虚假业务内容并违背用户体验/冻结资格。|

核查了 Handover create_version 服务与 HTTP 请求字段、现有详情页、AI 建议卡片和 Evidence 页面。前置不满足，按仓库编码前检查纪律停止 `HND-05-A02` 的正式编码；不把后台可调用视为用户可完成版本。下一独立任务 `CAP-02-A01`：核查已批准全局能力基线的用户发现/创建/评审路径与现有正式权限；并行独立任务随后检查项目 Evidence 到 Handover 候选的安全映射。若发现冻结合同或 Scope 需变化，先记录正式 CR。Pilot/Gate 状态不变。
