# AI-04-A06-P04-P01 Content Plan 持久化与 Preview 绑定前置核查

日期：2026-10-03；状态：`PASS`（设计前置）；依据 CR-AI-015/016、DEC-726～731、Schema0064/0068～0071。仅文档，无程序、Schema、API 运行行为、依赖或外发变化。

## 发现的时序冲突

当前 AI_TASK 顺序为 `Egress Preview → Authorization → Task Create`。Preview 请求只有 Provider/Model、业务 SourceRef、客户端 `estimated_record_count`/`payload_fingerprint` 和上限；Task 的 task type、Prompt policy、output/context policy 与参数直到最后一步才出现。因此现有 Preview 不可能构建 A01～A04 定义的完整 Content Plan，也无法证明其批准的是后来 Task 实际 Prompt/参数/Envelope。

不能选择“Task 创建时再生成 Plan”：审批已发生，后生成的 Prompt/参数没有进入批准内容。不能继续信任客户端 payload hash：客户端既无 ParseRecord/最小投影，也无服务端 PromptVersion、编码与 estimator 权威。不能把参数正文写入 Plan：会扩大持久敏感面，且冻结设计只要求参数摘要。

## 选定的兼容方案

1. 保持 URL 和 Preview/Authorization/Task 响应安全投影不变；非 `AI_TASK` 的 RETRIEVAL/INDEX 请求合同不变。
2. AI_TASK Preview 请求改为服务端计划模式：新增且强制精确 `ai_task_plan`，字段与后续 Task Create 的 `task_type / prompt_policy_ref / output_schema_ref / context_policy_ref / task_parameters` 一致；AI_TASK 不再接收客户端 `estimated_record_count` 和 `payload_fingerprint`。服务端解析 Input Owner、当前 Prompt/参数、Context policy、模型与 estimator，构建 Plan/Envelope 后返回既有两个计算结果字段。
3. 这是 AI_TASK 请求体的有意不兼容收紧，纳入 CR-AI-016/API Change 记录；当前尚无正式发行或可执行 Worker，前端与后端在同一发布切片升级。旧调用明确 400/422，不静默忽略旧 hash。Task Create 请求体不新增字段，通过 Authorization 反查唯一 Plan，并逐项比较原字段/参数摘要/SourceRef。
4. 旧 Preview/Authorization/Task 保留可读、可撤销和审计，但因无 ContentPlanRef 一律不可创建新 Task或执行，不猜测回填。非 AI operation 不要求 Plan。

## Schema0072 目标

- 新表 `ai_execution_content_plans`：一对一反向绑定 AI_TASK Preview，保存 Plan v1、Project/Purpose/Task、业务 Source 摘要、Prompt/参数摘要、Context 完整形态、Provider/Config/Model、策略/编码/Estimator、Content Plan hash、服务端 Envelope payload hash及记录/字节/Token计数；不存正文、参数值、locator、Secret、endpoint或Provider响应。
- 新表 `ai_execution_content_sources`：按 ordinal 保存业务 InputRef 与精确 Owner content revision/object、producer/schema/selection policy、source/result/projection 三类 hash、原始结果大小与最小记录数；ordinal 连续且语义唯一。
- `ai_egress_authorizations`、`ai_tasks`、`ai_egress_authorization_snapshots`、`ai_invocations` 增加可空 `content_plan_ref`；NULL 仅表示0072前历史。新 AI_TASK 写链必须非空并匹配同一 Preview/Authorization/Task，非 AI operation 保持 NULL。
- 数据库保护 Plan/Source 不可 UPDATE/DELETE/TRUNCATE；外键全部 `NO ACTION`，新 Plan 历史存在时 downgrade 拒绝。根/来源完整性采用 deferrable constraint trigger，允许同一事务先写根再写有序来源；应用层仍重算全部 fingerprint，不把 DB 形态约束当语义证明。
- Plan root 的 `payload_fingerprint/record_count/payload_bytes/input_tokens` 必须与 Preview 的计算值及上限相容；Authorization 只能缩小上限，不能换 Plan。Task/授权快照/Invocation 必须沿用同一 PlanRef，Invocation 的 request payload fingerprint 必须等于 Plan 服务端 Envelope hash。

## 实施切片与验证

- P04-P02：ORM + Migration0072；空库、0071历史库、旧AI/非AI记录、up/down/re-up、ORM drift、形态/不可变/有历史拒降。
- P04-P03：Content Plan PostgreSQL Repository/Owner 与事务级完整性复核，不改HTTP。
- P04-P04：AI_TASK Preview服务端构建/持久化及条件请求合同；非AI回归。
- P04-P05：Authorization/Task/Snapshot/Grant绑定同一Plan，旧NULL失败关闭；再进入Invocation/Adapter切片。

验证必须覆盖：同一 DocumentVersion 多ParseRecord、Prompt/参数/Plan/Envelope任一漂移；旧客户端hash不能放行；AI_TASK与非AI两类请求；并发幂等只生成一个Plan；正文/参数/locator不入库/repr/log；有Plan时拒绝down。Server 2025后续复验，Debian 13按用户指令跳过。

下一任务：`AI-04-A06-P04-P02`，实现 Schema0072 与 ORM，并仅验证数据库合同，不提前开放新 HTTP 或 Worker。
