# AI-04 Schema0074：SuggestionPayload 与 Evidence 引用归属

日期：2026-10-03；状态：`SCHEMA_PASS`；依据 CR-AI-018、DEC-753/754；上游 `20261003_0073`。

本增量追加不可变 `plm.ai_suggestion_payloads` 与 `plm.ai_suggestion_evidence_refs`，并把 `ai_invocations.suggestion_payload_ref` 变为延迟复合外键。每个 SuggestionPayload 唯一归属一个 Task/Invocation，必须与 RUNNING、尚未发布结果的 Invocation 保持 Scope、Project、Output Schema ref/version 一致；结构化载荷限制为 JSON object 和 1 MiB，指纹固定 SHA-256，业务事实状态固定为 `NOT_FORMAL_FACT`。Evidence 仅保存有界、类型化的 Owner/Object/Version/内容指纹引用，不复制原文。

结果建立期间允许先插入 Payload/Evidence，再在同一发布事务将 Invocation 指向 Payload 并终态化；发布后 Payload/Evidence 均不可增改删或截断。Schema VALID 只表示结构验证成功，不代表客户确认或正式业务事实。多态 Evidence 的实际 Owner 存在性和内容指纹将在 P07-P04/P05 由受信 Owner 复核，不能仅凭引用字符串宣称证据存在。

既有 Invocation 的 NULL `suggestion_payload_ref` 原样保留，不猜测回填。空结果历史可降回0073；一旦存在 Payload/Evidence 或非空结果引用，降级拒绝，须停止发布并向前修复或从受控备份恢复。Windows 11/PostgreSQL 18.6 已完成空库、历史库升降/重升、ORM drift、约束负例、延迟复合FK、发布封存和拒降验证。
