# AI-03 PromptVersion 激活首次结果 Schema 0061 增量

版本：0.1.0；日期：2026-10-02；依据 CR-AI-008。Gate 2 原冻结提交 `64cdf09` 与 0059/0060 历史保留。

新增 AI 自有 `ai_prompt_activation_results`：结果 UUID、模板/版本复合 FK、操作者、Audit、Trace、固定状态 `ACTIVE`、预期/首次结果 lock_version 与 UTC 时间/创建事务。通用幂等收据后续只引用结果 UUID，不通过当前可变根重建旧 200。结果不保存 System/User Prompt 正文、API Key 或客户资料，也不决定任何 Prompt 内容是否准入。

数据库约束要求非零身份、正版本号、`lock_version=expected+1`、跨模板复合归属和 Audit 唯一；UPDATE/DELETE/TRUNCATE 触发器禁止改写历史。同一模板/版本允许历史上的再次激活（不同结果），后续内部服务须按当前根状态/强版本、权限与 License 再决定是否可执行。根状态、Audit、结果及收据仍待应用服务放入同一事务。

Migration `20261002_0061` 由 0060 增量升级；空表可降级，有任何结果先锁表并拒绝降级，不物理删除历史。Windows 11 隔离 PostgreSQL 18 已验证空库 up/down/re-up、既有 Prompt 历史升级、ORM drift=0、复合 FK/形态/Audit 唯一与历史保护；正式库、目标账户、Server 2025、Debian 13、安装升级和 Gate3 未验。
