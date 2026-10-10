# SOL-03-A04-P03-P03-P06-A03-P01：GLOBAL 参考候选发布账本 Schema

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A03_P01_GLOBAL_PUBLICATION_SCHEMA_PASS`；仅封闭数据库结构，不代表管理员发布或项目端候选可用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入为 Gate 2 冻结 ReferenceSolution/Version、CR-SOL-018、DEC-1148、现有 0156 线性迁移和 GLOBAL 脱敏确认/资格事件模式。
- 单一问题：为人工审定的非敏感 GLOBAL 候选标签建立不可变、版本绑定且可撤回的发布事件历史。范围仅 Solution ORM、Alembic、测试与验证资产；不新增公开 API、角色或依赖。
- 前置已满足：GLOBAL Root/Version 复合身份、Auth 用户身份、统一拒绝 TRUNCATE 函数存在；发布 Owner/管理员确认尚无，因此数据库写入口必须关闭。
- 验收：空库及有历史库 up/down/re-up、ORM 漂移、GLOBAL 复合 FK、标签/原因/状态约束、直接 DML 与 TRUNCATE 拒绝、有事件拒降和后端回归。
- 风险：把旧 GLOBAL 数据默认为已发布、版本修订后沿用旧标签、数据库直写绕过人工审定或回退删历史。通过无回填、版本绑定、封闭 Guard 和非空拒降控制。

## 实施与验证

新增线性 `0156→0157` 表 `plm.sol_global_reference_publication_events`：UUIDv7 事件身份、固定 GLOBAL Root/Version 复合外键、每 Root 唯一正序事件号、PUBLISH/REVOKE、仅 PUBLISH 可携带去首尾空白且无控制字符的 1～160 字展示标签、必填 1～2000 字原因、Auth 操作人和有限时间戳。独立索引支撑版本事件读取。旧 GLOBAL 行无事件，保持未发布。INSERT/UPDATE/DELETE Guard 全拒，TRUNCATE 全拒；无事件可降级，已有事件拒降并要求前向修复。验证夹具绕过 Guard 仅为模拟未来合法事件并测试数据库约束，不是生产写入口。

Windows 11 一次性 PostgreSQL 18.6 脚本 `validation/sol-03-a04-p03-p03-p06-a03-p01-global-publication-schema/verify.py` 退出 0：空库、既有 GLOBAL Root/Version 库升降重升、无新 Alembic upgrade 操作、旧行默认未发布、复合 FK/Scope/标签/状态/原因约束、直接 DML/TRUNCATE 拒绝与非空拒降。定向单元 9 通过；后端全量 3471 通过、3 跳过、5333 子例通过。现有 Alembic HNSW 表达式及计算默认值比较警告保留，不把警告当 Schema drift。

兼容/回滚：无旧行变更和冻结 `/api/v1` 变化；部署须执行 0157，空事件表可退回 0156；有事件时不可逆向删表或删历史，关闭未来入口并前向修复。下一项 `SOL-03-A04-P03-P03-P06-A03-P02` 建立管理员发布/撤回 Owner、当前资格/确认/版本证明及 Audit/收据，之后再开放可选 HTTP、项目最小候选只读面和浏览器。Gate 3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-018 → DEC-1148 → 0157/本验收 → 发布 Owner → 项目候选读面。
