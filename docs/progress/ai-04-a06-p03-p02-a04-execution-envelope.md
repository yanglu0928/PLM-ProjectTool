# AI-04-A06-P03-P02-A04 确定性执行 Envelope

日期：2026-10-03；状态：`PASS`；依据 CR-AI-015/016、DEC-726～730。无 Schema、公开 API、依赖、Provider 调用、检索调用或客户数据外发。

## 实现

- 新增 `provider-neutral-json.v1` / v1 规范编码：把按 Plan 顺序且 hash 已复核的最小 source projection 组成 `ai-input-bundle.v1`，经已准入 Prompt 渲染后生成固定 system/user message、模型身份和结构化输出 schema 引用；UTF-8 JSON 使用固定 key 排序、无空格分隔、拒绝重复 key 与非有限数。
- 在 `AIExecutionContentSourceIdentity` 增加不含正文的 `projection_fingerprint`。Document Owner 在规划阶段从真实最小投影计算该 hash，执行阶段重新投影并复核；通用 Projection 自身也强制内容 bytes 与 Plan hash 一致。ParseResult 原始 hash 与最小投影 hash 分别保留，不相互冒充。
- `AIExecutionEnvelopeBuilder` 只接受与 Plan 数量、顺序和身份完全一致的 projection；Envelope 保存 Plan fingerprint、按序 projection hash、规范字节、记录数、字节数、Token 估算结果和 estimator 身份，正文与 hash 不进 repr。
- `require_envelope_for_grant` 复核完整 Content Plan、Envelope/Plan/Estimator 身份、服务端 payload SHA-256、记录/字节/Token 上限和有效期，再生成既有 `AITaskPayloadPlanProof`。客户端旧自报 fingerprint 不能通过，须由后续 P04 服务端 Preview/Authorization 持久化链生成。
- 新增显式 Context Policy Registry。本切片仅注册 `no-retrieval.v1 → NONE`；任何未知 NONE 或 `RAG_CONTEXT` 均失败关闭，不接受调用者自带 context 文本，不执行网络或检索。
- 新增可注入、版本化 Token Estimator Registry；只有 ref/version/model identity 完整一致的估算结果可用。提供 `utf8-byte-upper-bound.v1` 合成/候选实现，但明确要求目标 Adapter/模型 tokenizer 资格证明后才可在正式策略绑定，不能据名称宣称通用精确 tokenizer。
- 输入投影累计与 Envelope 设 100,000,000 bytes 绝对内存上限；授权可配置更小上限，不能放宽该硬限。

## 验证

- 定向 24 项 PASS：A04 新增6项，连同 Content Plan、Prompt/参数和 Document Owner 回归；覆盖确定性字节、投影 hash/顺序、RAG/未知 policy、未知/错误 estimator、payload hash、记录/字节/Token/时限和 repr。
- Windows 11 / Python 3.13 验证在 `socket.socket` 被强制拒绝期间两次构建完全相同 Envelope；服务端 fingerprint 与 payload proof 一致，Token 越限拒绝，RAG 失败关闭。标记：`AI_04_A06_P03_P02_A04_ENVELOPE_PASS`。
- A02、A03 的 Windows 11 / PostgreSQL 18.6 真实脚本随 projection hash 合同重跑 PASS；Invocation 数为0，无 Provider 调用。
- 后端全量：`Ran 2191 tests in 38.424s`，`OK (skipped=3)`。
- 开发 wheel SHA-256：`3e39c82a15758fc6521e0f74af8eb5c05da480db1fe02d931ed90e3862c52e1b`。

## 偏差、兼容与回滚

编码前确认 A03 的 ParseResult hash 能证明 Owner 原始结果，却不能让通用 Envelope 独立证明派生的最小 projection bytes，故在尚未持久化前追加 `projection_fingerprint`，登记 DEC-730。首次定向运行因补丁把该新字段误放入 `DocumentAIContentSource` 而非 `DocumentAIContentIdentity`，6个测试夹具均在构造阶段 TypeError；字段立即移至正确身份对象，未放宽规则，随后定向、A02/A03真实链和全量回归全部通过。无数据库或外部数据影响。

本项仍是未装配内部合同，复用 Schema0071，无 Migration、公开 API、生产 Worker 或网络 I/O。回滚可撤 Envelope/Registry 并回退 projection hash 内部字段；Document/Task/Authorization 历史不变。当前正式 Task Policy 使用的 `project-documents.v1` 需要 RAG，因 RetrievalRun/ContextBundle Owner 尚不存在，继续不可执行；不静默降级为空 Context。Windows Server 2025 未复验，Debian 13 按用户指令跳过。

下一任务：`AI-04-A06-P04`，以增量 Schema 持久化 Content Plan/Source 并重构 AI_TASK Preview、Authorization、Task 绑定；先完成编码前迁移/兼容核查。
