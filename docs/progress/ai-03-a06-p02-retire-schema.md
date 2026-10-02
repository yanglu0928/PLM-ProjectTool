# AI-03-A06-P02：Prompt 退役首次结果 ORM/Migration

版本：0.1.0.dev0；日期：2026-10-02；状态：Win11 隔离 PostgreSQL 18 Schema 验证 PASS；退役服务/API/生产迁移未实施。

Changed：按 CR-AI-009 新增 `PromptRetireResultRow` 和 Migration0062，保留 DRAFT/ACTIVE 退役前快照、同模板活动版本引用与不可变首次结果；空表可降，非空拒绝物理降级。实施中首轮迁移因自动外键名超过 PostgreSQL 63 字符失败，改为显式短名；第二轮负例发现 SQL CHECK 的 NULL 三值逻辑使 ACTIVE+空旧版本被接受，增加显式 `IS NOT NULL`；复验均通过。未更改原冻结基线。

Files：`modules/ai/infrastructure/prompt_orm.py`、`migrations/versions/20261002_0062_ai_prompt_retire_result.py`、Schema/迁移合同测试、隔离PG验证脚本、CR/决策/状态/版本说明。Migration：0062，空/有历史 up、空表 down/re-up、非空拒降。API/依赖：无。

Tests：Win11 隔离 PG18 脚本 exit0，drift=0、合法 DRAFT/ACTIVE、跨模板 FK、状态/空值/版本/Audit 唯一/历史不可变/非空拒降；随机库已删除。后端全量2085项通过、3项既有跳过；开发 wheel SHA-256 `833be57233163f092529fb88d5b427d985491bbdec199aefeb808b5b8c72c6f8`（临时输出未提交）。Golden Dataset 未运行：本项无模型调用。

兼容/升级/回滚：0061后增量；生产先备份并受控升级，尚未执行；有结果时须保留历史并向前修复。Known Issues：Schema不等于退役可用；内部服务、HTTP、Invocation 资格、正式信任/目标账户、Server2025/Debian、Gate3/UAT/可用包未验。Next：`AI-03-A06-P03` 内部退役服务及隔离PG18权限/并发/重放/回滚。
