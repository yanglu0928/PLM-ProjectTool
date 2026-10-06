# SUR-03-A02：Assignment/Response 四表 Schema0108

日期：2026-10-06。结论：`SUR_03_A02_RESPONSE_SCHEMA_PASS`。下一项：`SUR-03-A03` Assignment create/list/get、目标与当前角色 Owner。

## 实现与验证

- 新增冻结 SRV-04 四表 ORM 与 Migration `20261006_0108`：Assignment 固定 Round/Version/部门/可空受访人，Response 固定单问题、来源与更正前驱，Answer 一对一保存 typed/raw value，Evidence ref 固定 DocumentVersion/lock/fingerprint。
- 数据库强制 OPEN Round 与固定 target department、当前有效assignee成员、`NULLS NOT DISTINCT` target唯一、单根单后继更正、一Response一Answer、FACILITATED_RECORD Round source、PROJECT Evidence快照和四表不可更新删除截断；有历史拒降。
- Windows 11/PostgreSQL 18.6 完成非空/空升级、空历史降级重升、drift、Round/target、唯一、更正分叉、一对一Answer、Evidence、不可变和历史拒降；后端 `2880 passed / 3 skipped`、`4154` 子断言；wheel `1070` 项，SHA-256 `d0ff7af0146bd2ed8746fddf2d38d21037e4f543e604d9476e4907a6d0ced6b5`。
- 首轮真库验证发现多表共用触发器在 Answer 行上求值 Evidence 专属字段；改为按表名外层分支后从新数据库完整重跑。首轮全量回归另发现迁移 head 与 ORM inventory 断言仍停留0107，更新为0108/四表后全量重跑通过。

## 兼容与回滚

只新增冻结已有四表，不改现有表、公开API、依赖、Secret或外发。空历史可降0107；存在SRV-04历史只能停止后续Owner/Router并向前修复，不得删除答复事实。当前尚未开放业务写Owner，Round CLOSE继续失败关闭。
