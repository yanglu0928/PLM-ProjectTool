# CR-PLAN-003：补齐 Plan WBS 的 Prototype 固定版本引用

日期：2026-10-26。状态：`IMPLEMENTED_PASS_SCOPE_LIMITED`；仅关系 Schema 片验证，非 Gate 通过。

## 来源与冲突

冻结 Gate 2 的 DM-05 将 WbsItem `requirement/solution/prototype refs` 列为固定业务版本映射。Plan 0186 的 `pln_item_solution_refs` 只表达 Outline、Section、StructuredSpec；未定义 PrototypeVersion 引用。Prototype 侧已有不可变 `prt_prototype_versions`，含 `(prototype_version_id, prototype_id, project_id)` 唯一键。若 PlanVersion Owner 忽略 `prototype_refs` 会静默丢失冻结输入；若只存裸 UUID/JSON，又不能证明固定版本/Project 归属。

## 方案与选择

- A：拒绝所有含 Prototype 引用的计划。可暂时失败关闭，但不能实现完整冻结输入，不能作为最终行为。拒绝为交付方案。
- B：将 PrototypeVersion ID 放入通用 JSON/无 FK 字段。无法保证版本身份、项目隔离、反向查询和后续 Trace；拒绝。
- C（选择）：Migration `20261026_0187` 增加 `pln_item_prototype_refs` typed owned rows，固定 `wbs_item_id/plan_version_id/plan_id/project_id` 与 `(prototype_id, prototype_version_id)`；Project/Version 两侧使用复合外键，按 ordinal 保序并去重。新表在 Plan Owner 未安装时保留写入/更新/删除/截断失败关闭保护。

## 兼容、风险与回滚

- 不修改冻结 API、请求字段或既有 Schema；在 0186 后只追加表。无既有行需要回填，不改变用户数据。
- Prototype 固定版本引用在 Plan Owner 中仍须证明目标属于当前项目，且引用具备冻结要求的有效批准状态/当前指针；FK 仅证明身份/归属，不代表 Approved。
- 空库可逆向降级；表中一旦有业务引用，降级必须拒绝，采取关闭写入口并向前修复，不删除正式快照。
- 验证：PostgreSQL 18.6 在 0186 schema 上升级/降级/重升、drift；跨项目、错 Prototype 身份/版本、重复目标和删除历史负例；完整后端回归。未实施前不宣称完成。

## 授权

按用户 2026-09-24 持续授权，发现与 Gate 2 冻结语义不兼容后先登记 CR、保留原 `64cdf09`，自主按方案 C 实施与验证；不改变业务语义，仅补齐强类型持久表达。

## 实施状态

- Migration `20261026_0187` 与 `PlanWbsPrototypeRefRow` 已追加；关闭式Owner/no-truncate guard和有历史拒绝降级已实现。
- PostgreSQL 18.6 空业务库0186→0187→0186→0187与drift通过；没有验证有历史行上的升级/降级或真实跨Project FK负例。详见 `docs/progress/plan-02-a04-p04-a04-p03-p04-s03-p02-prototype-schema.md`。
- 后续Plan Owner仍须证明当前批准Prototype及Review，不得由FK证明替代业务资格。
