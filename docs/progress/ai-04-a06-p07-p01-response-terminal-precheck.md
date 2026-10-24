# AI-04-A06-P07-P01 Provider 响应、Suggestion 与 Invocation 终态前置核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_SPLIT`；依据冻结 ADR-004/DM-04/API-03、Schema0064/0073、CR-AI-015～017、P06-P05-P04。

核查确认现有 Adapter 已能返回有界、可清零 `AIProviderResponse` 与 fingerprint/usage/latency/finish observation，但尚未解析 `message.content` 的结构化建议，也没有 Output Schema registry。数据库只有未绑定的 `suggestion_payload_ref`，不存在 SuggestionPayload表、FK或受权正文 Owner，不能把自由UUID或原始Provider wrapper当成可读建议。

更关键的是 P06 发送时 Invocation 仍为 `PENDING`。进程在网络副作用后崩溃会让同一记录继续满足 pre-send，可能重复外发。登记 CR-AI-018：第二次pre-send稳定后、Adapter前必须原子 `PENDING→RUNNING` 形成持久发送栅栏；RUNNING后禁止相同Invocation再次pre-send。网络/进程结果未知沿用冻结状态机，发布为 `FAILED + AI_PROVIDER_OUTCOME_UNKNOWN + retryable=false`，不新增Breaking枚举；显式Retry只能创建新 attempt。

实施拆为：P02 SuggestionPayload/0074；P03发送栅栏并接回P06编排；P04受信Schema registry与最小响应解析；P05成功Suggestion/Invocation/Task/Job/Audit原子发布；P08失败/UNKNOWN/取消/对账/显式重试。schema VALID仍不是业务事实，输出固定 `NOT_FORMAL_FACT`，AIService不得直接写 Requirement/Solution/Plan 等正式表。

Changed/Files：新增CR-AI-018、DEC-753、本进度、状态和版本说明。Migration/API/Dependencies：本项无。Tests：静态核对冻结DM/API、Schema0064/0073触发器/ORM、P06 Adapter/发送编排及仓库不存在的Suggestion/Schema Owner；未运行新增代码或外发，不标终态PASS。Compatibility/Rollback：本项仅设计；后续0074保留旧NULL历史并拒绝有结果历史的物理降级。Known Issues：P02～P05/P08均待实施；真实Provider/客户数据未调用，Server 2025、Gate 3/UAT/可用包未完成。Next：`AI-04-A06-P07-P02` SuggestionPayload owned Schema0074与真实FK。
