# AI-03-A04-P01：不可变增版首次结果 Schema

版本：0.1.0；日期：2026-10-02；结果：隔离 Schema PASS；PromptVersion 写命令/内容准入/公开 API 未实现。

Changed：按 CR-AI-006/DEC-677，在 0059 后新增 AI 自有 `ai_prompt_version_create_results` ORM/Migration 0060、不可变触发器、复合版本 FK 和独立结果 UUID，供后续通用幂等收据引用；不复制正文、不开放模型调用。

Files：`apps/backend/src/plm_assistant/modules/ai/infrastructure/prompt_orm.py`、`apps/backend/src/plm_assistant/migrations/versions/20261002_0060_ai_prompt_version_create_result.py`、迁移/元数据测试、`validation/ai-03-a04-p01-version-result-schema/verify.py`、CR/决策/Schema 增量/状态。

Migration：0059→0060。Win11 隔离 PostgreSQL 18 空库 up/down/re-up、有已有 PromptVersion 历史升级、Alembic drift=0、缺版本复合 FK、错误指纹/乐观版本、重复版本结果、UPDATE/DELETE/TRUNCATE 及非空降级拒绝已实测通过。正式生产迁移未执行；有结果历史时仅可向前修复。

API：无变更或挂载。兼容：Windows 11 隔离库；正式目标账户、Server 2025、Debian 13 未验。回滚：空表可降回 0059；非空不能物理删除历史。

Tests：迁移合同/ORM 元数据定向 7 项通过；后端全量 2055 项通过、3 项跳过；开发 wheel 构建通过，SHA-256 `74ac116e7bc45b7e57d4d5c2625c5a4e72b01b59e493da6e71e9ef70de11cc40`（包不提交）。

Known Issues：准入来源尚无生产装配；仅靠正则/哈希不能证明正文不含客户固定副本、Golden 答案或绕过指令。后续 P02 必须在同事务写入版本、结果、Audit、收据并维持缺准入失败关闭；Gate 3/UAT/可用包未完成。Next：`AI-03-A04-P02` 规范化内容、准入证明与内部原子增版。
