# CR-AI-016：AI 执行内容必须绑定不可变 Content Plan

日期：2026-10-03；状态：依 V1.1 持续授权登记，待分片实施；关联 Gate 2 冻结提交 `64cdf09`、DM-04、API-03、CR-AI-015、Schema0064/0068～0071。WBS `AI-04-A06-P03-P02`。

## 冲突与证据

冻结合同要求 `AITask` 固定不可变输入版本，每次 `AIInvocation` 保存实际发送的 Input/Context 版本和载荷摘要；Prompt、Input、Context 或 source version 变化时不能伪装成确定性重放。现有实现只在 Task/Egress Preview 中固定 `DocumentVersion`，而 Document Owner 读取解析正文必须同时提供唯一 `ParseRecord`。同一 `DocumentVersion` 可以因 parser profile/version 或重试产生多个成功解析结果，因此 Worker 运行时选择“最新成功解析”不能唯一复现批准时正文。

当前 `EgressPreviewService` 还接受客户端提交 `payload_fingerprint`，并把 `source_refs_fingerprint` 直接计算为业务 InputRef 集合摘要；Task 创建继续要求该摘要等于 Task InputRef 摘要。这一结构没有位置保存 `ParseRecord`、ParseResultRef/hash、正文编码策略、模板渲染版本或 Token estimator 身份。发送原文件字节会改变 `minimum.document.text.v1` 的语义，也不能替代解析文本批准。

仓库尚无 `rag` 模块、`RetrievalRun` 或 `ContextBundle` 生产实现。已有 Task Policy 可引用 RAG/context policy，但执行器不能把未实现的 policy 静默解释为“无 Context”。Prompt 正文和最小参数已经存在于各自 Owner 数据中，但当前 Grant 仅投影哈希；Envelope 构建器不能直接跨模块查表或从哈希猜正文。

## 方案比较与决定

- A：执行时选择最新成功 ParseRecord。否决；解析结果改变会使已批准载荷漂移，并破坏重试确定性。
- B：把原始 Document 文件作为 Provider 输入。否决；与已批准的最小文档文本策略不等价，并扩大外发类型与载荷。
- C：把 ParseRecord 当成公开 AITask 输入，替换现有 DocumentVersion。否决；会把文档模块内部处理身份泄露为业务输入，并对冻结 `/api/v1` 形成不必要破坏。
- D：Preview 阶段由服务端解析业务 InputRef，建立独立、不可变的 `AIExecutionContentPlan`，固定精确内容来源、渲染/编码/估算策略；Authorization 和 Task 只引用并复核该 Plan。选择 D。

## 目标模型与边界

1. `AITaskInputRef` 继续表示用户选择的业务输入版本；不得由 ParseRecord 替代。
2. `AIExecutionContentPlan` 是 AI Owner 的不可变执行快照，至少固定：Project/Scope、按序 InputRef、每项 Owner 内容来源身份、PromptVersion、参数摘要、context policy、正文最小化策略、Envelope 编码版本、Token estimator ref/version 和整体 fingerprint。
3. Document 内容来源必须由 Document Owner 投影并包含精确 `DocumentVersion`、`ParseRecord`、ParseResultRef、Parser profile/version、源文件 hash、结果 hash 和受权内容读取证明。AI 模块不得直读 Document 表或 storage locator。
4. Prompt 内容由 Prompt Owner 按 Grant 中的精确 template/version/hash 投影；任务参数由 AI Task Owner 按已持久化摘要投影。内容只存在于短生命周期内存对象，不进入 Job、Outbox、Audit、普通日志或异常。
5. RAG policy 只有在受权 `RetrievalRun`/不可变 `ContextBundle` 实现并进入 Plan 后才可执行；明确版本化的无检索策略可生成空 Context。未知、未实现或需要 RAG 的 policy 失败关闭。
6. Egress Preview 的不可变 source refs 仍展示业务 DocumentVersion，另外以安全摘要标识 Content Plan；浏览器不接收解析正文。AI_TASK 的最终 payload fingerprint 必须由服务端同一 Envelope 构建器计算，不接受客户端自报值作为放行依据。
7. Task 创建必须绑定授权对应的 Content Plan；每次 Invocation 再读取同一 Plan、重建 Envelope，并逐字节核对 fingerprint、字节/Token/记录上限和当前授权。Plan 或来源变化必须新建 Preview/Authorization/Task。

## 实施顺序

1. `P03-P02-A01`：定义无正文 Content Plan、内容来源身份和 Owner Port 合同，覆盖严格校验与规范化 fingerprint。
2. `P03-P02-A02`：实现 Prompt/Task 参数内容 Owner 与严格、无动态执行能力的模板渲染器。
3. `P03-P02-A03`：实现 Document 解析内容 Owner，以精确 ParseRecord/结果 hash 读取并前后复核，完成 Windows 11/PG18.6/本地文件正负链。
4. `P03-P02-A04`：实现 provider-neutral Envelope 规范编码和可注入、版本化 Token estimator；只接受明确支持的 context policy，不执行网络 I/O。
5. `P04`：以增量 Schema（编号在实现切片分配）持久化 Content Plan 及来源行，重构 AI_TASK Preview/Authorization/Task 绑定；非 AI operation 保持原合同。此切片再更新 ORM、Migration、API 文档和兼容测试。

## 兼容、迁移与回滚

- 原 Gate 2 冻结提交和现有 0064/0068～0071 历史不改。P03-P02-A01～A04 先建立未装配合同与 Owner，暂不产生数据库或公开 API 变化。
- P04 采用追加表/引用的全空或完整兼容迁移：旧 Preview/Authorization/Task 保留只读，但因缺少服务端 Content Plan 不可执行，也不猜测回填；新 AI_TASK 链必须完整绑定。非 AI Egress 操作不受该执行门禁影响。
- 公开 `/api/v1` 保持已有业务 source refs。AI_TASK 客户端载荷摘要字段的兼容处理必须在 P04 的 API 增量文档中明确：服务端不再信任该字段，不能用静默接受客户端摘要冒充服务端证明。
- 回滚优先撤销 Worker/AI_TASK Preview 新组合并恢复不消费；不可变 Plan、Task、Authorization、Invocation 和 Audit 历史保留。若新 Plan 已有引用，不做破坏性降级，采用向前修复或受控备份恢复。

## 验证计划与剩余风险

- 单元：规范化 fingerprint、顺序、重复/未知 Owner、Prompt/参数 hash、模板占位符、UTF-8/NFC/换行、字节与记录上限、Estimator 身份/上限。
- 集成：同一 DocumentVersion 多 ParseRecord 必须只接受 Plan 指定结果；结果 hash、Parser version、授权、Project、Context 或 Content Plan 一字节漂移均在外发前拒绝。
- Migration：空库、有旧 Preview/Authorization/Task 的升级，up/down/re-up、ORM drift、完整性和不可变负例；有新 Plan 引用时拒绝物理降级。
- 安全：正文、模板、Task 参数、storage locator、Secret 不进入 repr/log/Audit/Job/Outbox；无支持的 RAG Context 时失败关闭。
- 真实 Provider 外发不由本 CR 自动授权。本阶段只使用合成内容；客户正文外发仍需该轮明确范围与用途授权。

剩余风险是 Provider tokenizer 差异、超大解析结果的内存边界、读取期间撤权和 RAG 尚未实现。控制为 Adapter/模型绑定的 estimator、内容长度硬上限与分片策略、读取前后复核以及未支持 context policy 关闭执行。
