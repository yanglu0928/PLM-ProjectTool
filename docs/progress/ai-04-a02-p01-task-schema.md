# AI-04-A02-P01：AITask Root/输入版本 Schema

日期：2026-10-02；版本：0.1.0.dev0。Changed：依据 DEC-698 新增 AI-owned ORM、Alembic 0063、不可变输入引用及 Scope/Project 归属与终态保护；更新 Alembic 注册、迁移/ORM 清单测试。Files：`task_orm.py`、`20261002_0063_ai_task_identity_inputs.py`、`migrations/env.py`、验证脚本及本 Schema/进度/决策/状态/版本说明。

Migration：Win11隔离PG18空库 up/down/re-up、有用户与项目历史升级、drift=0，合法GLOBAL/PROJECT、跨项目/错误Scope/坏指纹/重复序号拒绝，输入修改/删除/截断、运行后追加、Root身份改写/终态复活、非空降级拒绝 PASS。首轮全量回归因旧 ORM 和 migration-head 精确清单失败，更新清单后全量2100运行/3跳过 PASS。开发wheel SHA-256 `b411179e3422b9c4fd28b887e575f1399315a90a0c1ef195fd53de9b372660cc`，非交付包。

API/依赖/外发：无；没有厂商调用。兼容/升级/回滚：仅新增表，部署前备份并受控升级；空表可降，有历史拒降并保留数据。Known Issues：Invocation/Context/授权快照及当前Attempt指针、输入真实版本/Owner权限核验、正式信任/账户、Server2025/Debian、Gate3/UAT/可用包未完成。Next：`AI-04-A02-P02` 补全 Invocation/Context/逐次外发授权快照物理表并验证；P01不代表 AI-04-A02 全部完成。
