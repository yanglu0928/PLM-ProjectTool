# HND-05-A02-P03：交接分析问题卡片版本创建页

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / PACKAGED_EDGE_PG_PENDING`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `HND-05-A02-P03`；只接已有冻结 Handover Version 创建的可操作页面。|
|输入基线|Gate 2 冻结 HND-01 `/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions`；`HND-05-A02-P01/P02` 私有提交与来源指纹；`CAP-02-A05-P03-P02-A03` 已批准能力合成链；`EVD-05-A03-P03` 有资格项目证据合成链。|
|前置任务|后端要求 ACTIVE 分析、原分析固定来源集、CURRENT_APPROVED 能力版本、1～500 项问题；非缺源项必须引用同项目 ELIGIBLE Evidence。现有项目文档/版本、能力基线/版本/条目、Evidence 列表和 Viewer 均有只读客户端。|
|模块/实体/API|HandoverAnalysis/Version/Item、DocumentVersion、CapabilityBaselineVersion、Evidence；只调用现有 GET/POST，不改 Schema/API。|
|权限|仅当前项目 PROJECT_MANAGER/IMPLEMENTATION_MEMBER 可写；页面预筛不是授权，服务端逐操作重验。GLOBAL 能力审批不由项目角色代替；证据资格不等于客户确认。|
|验收|页面选择同项目固定文档并匹配分析来源指纹；只选择当前批准能力版本和同项目 ELIGIBLE Evidence；卡片逐项人工编辑、字段提示、原文定位、DRAFT 明示；原操作正文/Key/ETag 在不确定结果下保持；同项目/身份路由变化清屏。前端定向与全量/typecheck/build；真实 Edge/PG/包内留 P04。|
|风险|首版本没有可读来源列表，需用户重选；卡片界面第一片支持六类问题、每项至少一条证据，但 NEED_CONFIRM 暂只支持一个输入字段与两个选项。AI 建议不自动变成问题。服务端仍是固定来源/资格最终权威。|

编码前结论：前置满足；无基线变更。完成后仅能宣称前端页面合同，通过实际包内 Edge/PG 前不得宣称业务链验收或 Pilot 可用。

实施结果：新增 `/projects/:projectId/handover/:analysisId/versions/new` 页面和分析详情入口。页面仅供现有项目编辑角色使用；按分析来源指纹复核手选固定文档版本，读取当前批准 GLOBAL Capability，筛出与所选固定来源完全对应的 ELIGIBLE PROJECT Evidence。问题卡片支持六种类型、多项、标题/陈述/影响/严重度/优先级/处理建议、证据原文定位和可选标准能力引用；`NEED_CONFIRM` 第一片提供一项必填信息（名称/格式/示例）与 A/B 两个方案，要求用户实际填写，不自动采用 AI 建议。每次提交用现有客户端创建不可变 DRAFT；原内容/Key/ETag 先保存在同源浏览器会话，网络不确定时只允许经用户核对后按原操作重试。路由/身份变化清屏，畸形已存操作闭锁。

定向5项覆盖有来源 DRAFT、两张卡片含待确认字段、错误来源/无编辑权限、未知结果原号重试和损坏存储闭锁；前端全量1974项及 typecheck/build 退出0。首次定向中损坏存储提示被初始加载清空，已修复并重跑通过。此为前端合同证据，不是实际数据库版本创建或客户确认；真实 Edge/HTTPS/PG 与打包验收留 `HND-05-A02-P04`。页面仅用浏览器会话保存待确认操作以便原号重试，可能含用户输入的候选问题文字；不提交 Git，不发送外部 AI。首版本仍需重选原固定文档，复杂 NEED_CONFIRM 的多字段/多方案编辑需后续增强；服务端仍为权限、来源、批准版本和资格最终权威。
