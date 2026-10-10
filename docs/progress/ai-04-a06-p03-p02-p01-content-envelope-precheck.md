# AI-04-A06-P03-P02-P01 内容 Owner 与确定性 Envelope 编码前核查

日期：2026-10-03；状态：`PASS_WITH_RECORDED_CHANGE`；无外部调用、无客户数据外发。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase|Phase 2 Platform Core|
|当前 WBS|`AI-04-A06-P03-P02-P01`|
|输入基线|Gate 2 冻结 DM-04/API-03/Application Contracts、CR-AI-015、Schema0064/0068～0071|
|前置任务|`AI-04-A06-P03-P01-A03` 完整 Execution Grant PostgreSQL 投影 PASS|
|涉及模块|`ai`、Document Owner Port；后续 `rag` 只通过正式 Application Port|
|涉及实体|AITask、EgressPreview/Authorization、PromptVersion、DocumentVersion、ParseRecord/ParseResult、AIInvocation/ContextRef|
|涉及 API|本项不修改公开 API；后续 P04 保持冻结路径并记录兼容增量|
|涉及权限|同 Project 输入/正文重授权、逐次 Egress Authorization、无权限统一失败关闭|
|验收标准|证明最终正文来源、Prompt/参数、Context、编码与 Token 估算可被不可变身份唯一复现；旧不完整记录不可执行|
|风险|DocumentVersion 与 ParseRecord 未绑定；客户端摘要不可信；RAG 未实现；Tokenizer 因 Provider 不同|

## 静态证据

1. `AITaskInputRef` 和 Egress Preview source ref 只保存业务 Object/Version；当前 `source_refs_fingerprint` 直接由 InputRef 集合计算并与 Task 输入摘要相等。
2. `DocumentFixedSourceProofService` 只有在调用方提供 `parse_record_id` 时才返回经过 source/result hash 复核的 `parse_content`；其结果还固定 ParseResultRef、parser profile/version 和结果 hash。
3. `doc_parse_records` 允许同一 DocumentVersion 按 parser profile/version 存在不同记录；数据库没有“业务输入版本唯一对应一个正文”的不变量。
4. 冻结 DM-04 已明确 DocumentChunk 的不可变来源为 `DocumentVersion + ParseRecord`，且 Invocation 的 Input/Context 变化不得伪装成确定性重放。
5. PromptVersion 正文按 NFC、LF、UTF-8 规范化并持久化 hash，但当前 Execution Grant 只携带 hash；任务参数同样只携带 fingerprint，必须通过 Owner 读取并复核，不能由 Envelope Builder 直接查表。
6. 仓库当前没有 `rag` 模块、RetrievalRun 或 ContextBundle 生产实现。已有 `context_policy_ref` 不能被静默降级为空 Context。

## 结论与选择

现有边界不足以安全实现完整 Envelope，直接编码会把“最新 ParseRecord”或“无 Context”变成未记录的动态决定。依据持续授权，已建立 `CR-AI-016` 并选择服务端不可变 `AIExecutionContentPlan`：业务 InputRef 保持不变，由 Preview 阶段解析并固定精确内容来源、Prompt/参数、Context、编码和 estimator 身份；Authorization、Task 与 Invocation 逐层绑定同一 Plan。

旧 AI_TASK Preview/Authorization/Task 因没有该服务端 Plan 只能保留历史、禁止执行，不进行推测回填。明确无检索的版本化 context policy 可以生成空 Context；任何需要 RAG 而平台尚未支持的 policy 失败关闭。

## 验收结果

- 冻结合同、当前 ORM/服务、Document Owner 与 Prompt 规范化实现已完成静态交叉核对。
- 新增偏差已在 `CR-AI-016` 记录方案比较、影响、迁移、回滚和验证计划；原冻结文件未改写。
- 本项不含程序、Schema、依赖、API 或运行行为变化，因此未运行代码测试，不宣称 Envelope/Worker PASS。
- 下一任务为 `AI-04-A06-P03-P02-A01`：实现无正文 Content Plan 与 Owner Port 合同。
