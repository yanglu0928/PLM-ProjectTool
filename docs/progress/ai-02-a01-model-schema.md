# AI-02-A01：部署 AIModel 身份与能力 Schema

日期：2026-10-02；状态：Windows11 / 隔离 PostgreSQL 18.6 限定范围 PASS。依据 DEC-664、冻结 DM-04、SC-01/02、API-03；Gate 2 原冻结内容不变。

Changed：新增 `ai_models`、`ai_model_capabilities`、`ai_quality_profile_refs` ORM/Migration `20261002_0057`。模型语义身份固定 Provider/key/kind/revision/dimension，EMBEDDING 维度强约束；初态 SUSPENDED。能力与质量引用只增，主表语义字段不可改；不在本项实现管理命令、模型路由或外部调用。

Tests：`validation/ai-02-a01-model-schema/verify.py` 使用新隔离 PostgreSQL 18.6，空库 up/down/re-up、有 Provider/Secret/Auth 历史升级、ORM 漂移 0、重复/null 语义、维度缺失/越界、跨 Provider、非法质量引用、历史修改/删除拒绝、仅状态字段可变以及有历史时拒绝降级均通过。后端全量2032项运行/3跳过，首轮 ORM 历史清单漏登记新表导致1项失败，修正测试清单后重跑通过；开发 wheel SHA-256 `cf1080c85fa4bfe59b3f714f3daceae43f58d9af9972ab66c4f2e83a40620b04`。临时数据库已停止；本项不接触客户数据或外部模型。

Migration：0056→0057；空库可 down，有历史拒绝 down。API：无变化。兼容：PostgreSQL18、原 Provider 表；无新依赖。回滚：未写模型时降至0056；有历史时保留并向前修复，不自动删除。Known Issues：质量引用尚未核验真实质量证明，模型可用性/Provider ACTIVE/路由/权限/Audit/API、Embedding 重建及正式发行环境均由后续 WBS 验收；Gate3/UAT/可用包未完成。Next：`AI-02-A02` 模型创建内部命令（Provider 归属、能力、语义唯一、初态与 Audit/幂等）。
