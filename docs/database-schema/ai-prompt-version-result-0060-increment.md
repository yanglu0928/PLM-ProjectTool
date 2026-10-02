# AI-03 PromptVersion 首次结果 Schema 0060 增量

版本：0.1.0；日期：2026-10-02；依据 CR-AI-006。Gate 2 原冻结提交 `64cdf09` 及 0059 历史保留。

`ai_prompt_version_create_results` 是 AI 自有、不可变的首次 `201` 结果索引：结果 UUID、模板/版本复合 FK、操作者、Audit、Trace、规范化内容指纹、预期/结果乐观版本与 UTC 时间。通用幂等收据后续只引用结果 UUID；同一 `(template_id,version_no)` 和 Audit 各只允许一个结果。表不复制 System/User 正文，也不保存 Secret/客户数据。

数据库约束校验非零身份、32 字节指纹、`lock_version=expected+1`、复合版本归属和历史不可变；它不证明指纹对应的正文已通过内容审查。版本、根版本更新、结果、Audit、收据须由后续应用服务放入同一事务。

Migration `20261002_0060` 从 0059 增量升级。空结果表可降级；若已有任何结果则锁表后拒绝物理降级并向前修复。Windows 11 隔离 PostgreSQL 18 已验证，正式库、目标账户、Server 2025、Debian 13 未验。
