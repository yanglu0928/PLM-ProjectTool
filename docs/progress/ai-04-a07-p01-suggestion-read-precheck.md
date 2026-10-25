# AI-04-A07-P01 AI 建议读取与定位前置核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_V2_SPLIT`；依据冻结 API-03、CR-AI-020、DEC-770/771。

编码前检查：当前 Phase 2；WBS `AI-04-A07-P01`。输入为 Gate 2 API-03、Schema0072/0074/0075、AI-04 Task/Worker闭环、Document固定ParseResult/Evidence Viewer和用户确认的交互要求。涉及 ai/document/jobs/platform；实体 AITask、AIInvocation、SuggestionPayload/EvidenceRef、ContentPlan/Source、ParseRecord；API为冻结 Task List、Invocation List、Suggestion GET；权限为创建者/项目管理角色及每个Document当前授权。验收要求是稳定分页、安全DTO、精确节点定位、明确人工补充提示、V1历史降级标识和零正文/Secret/路径泄露。

静态证据：后端仅实现Task Create/GET，前端无AI模块；当前V1 canonical item只有`source_ordinals`，`ValidatedAIOutput/ParsedAISuggestion`也只保留去重文档序号。虽然发送给模型的`document.minimum-text.v1`含稳定node_id，发布器将其降为文档级EvidenceRef，无法可靠恢复具体引用位置。现有Evidence Viewer能验证规范locator，但Suggestion没有Evidence实体ID或locator，不能直接复用其URL。

按CR-AI-020采用新`gap-output.v2@2`、服务端节点集合验证和Document-owned locator解析；V1不删除、不冒充精确。Task/Invocation列表使用同一独立Vault key但不同AES-GCM family/AAD，避免增加两个账户秘密同时保持协议域隔离。Suggestion GET不分页；返回canonical schema受控items及服务端citation descriptors，不返回原始Provider响应或无界原文。Accept/Reject保持关闭。

本项仅文档与变更登记，无产品代码、Schema/API运行或外发，未运行新增测试。Next：`AI-04-A07-P02` 实现 `gap-output.v2@2`、精确node引用验证和V1回归；先不开放HTTP。
