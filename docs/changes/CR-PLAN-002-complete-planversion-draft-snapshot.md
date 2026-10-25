# CR-PLAN-002：补齐 PlanVersion 冻结草稿快照的持久化字段

日期：2026-10-26。状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-001`（逐片验收中；不是 Gate 通过）。Gate 2 原始冻结提交 `64cdf09` 保留，不追写。

## 来源与冲突

P04 编码前核查发现冻结 DM-05/API-04 的 `PlanVersionInput`/`WbsItemInput` 语义范围大于现有 0170～0177 关闭式 Schema：ORM 当前可保存 PlanVersion/WBS 身份、FS 依赖、Milestone 与 Requirement/Solution/Evidence 固定引用，但尚不能完整保存日历/版本排除声明、任务类别、项目责任人/协作角色、计划与实际日期/工期、进入条件/验收条件及风险/显式排除；WBS output refs 目标 `OutputArtifact` 也没有已安装的 ORM、Migration 或 Owner。

DEC-20261019-1231 已明确这些字段留待后续，且在完整快照 Owner 接线前不开放写入。直接按现表创建 PlanVersion 会静默丢弃冻结请求或留下无法安全追溯的引用，故不得照现状开放写口。

## 方案比较与选择

- A：只保存当前身份字段，忽略请求里其余字段。拒绝：冻结请求与数据库快照不一致，会产生不可恢复的信息丢失。
- B：将完整 WBS/PlanVersion 输入整体打包进一个 JSONB。拒绝：无法由数据库证明 ProjectMember 归属、跨版本固定引用、排序/去重及未来 Trace 查询；与现有强类型子表重复存储并引入双写漂移。
- C（选择）：在原关闭式 Schema 上按冻结语义增量增加必要的强类型列/owned child refs；核心用户/项目/版本/业务引用继续使用复合 FK，有序简单文本集合使用 typed child rows。保留 `PlanVersionInput` 字段语义，不变更 `/api/v1` 请求合同。责任人使用固定 `ProjectMember` 身份，不以裸 user UUID 越过项目归属；无 OutputArtifact Owner 时拒绝非空 output refs，不把 UUID 伪装成已证明引用。

## 差异、安全与兼容

- 原冻结 Gate 2 文件和提交 `64cdf09` 不改写；这是针对已冻结 DM-05/API-04 的后续物理 Schema 完成和实现偏差记录，新增迁移在 0185 后顺序追加。
- 新列/child rows 只服务于新增 PlanVersion 草稿；历史空表无需回填为虚构事实。不得默认责任人、日历、非空条件或“无需专项”。
- 不改变角色授权、License、Review状态或 API 路径。写 Owner 仍须在事务内授权并验证来源、幂等和 Audit；Schema 扩充本身不开放业务写入。
- 尚无 OutputArtifact Owner/目标表：本变更中的 PlanVersion 写链对非空 WBS output refs 失败关闭，保持可空的 V1 快照能力；后续须待 OUT-02 Owner/复合关系可证明时另行启用，不能弱化成裸 ID。

## 迁移、回滚与验证计划

- ORM 与新的 Alembic revision 在 0185 后增量实现；使用复合 Project/Version FK、白名单状态/role/category/check、有限文本/数组约束和不可变触发器，不删除/重建旧 Plan 表。
- PostgreSQL 18.6 临时库覆盖空库升级、已有 Plan/PlanVersion 历史升级、新行写入后升降/重升、跨 Project Member/Plan/Version 错引用、重复/排序/形状/日期关系/非法 role/category/多目标或零目标排除负例和 Migration drift。
- 回滚优先关闭新写入口并向前修复。新字段或 child rows 已有历史后，降级必须主动拒绝，禁止删除正式版本快照；空库可按反向依赖顺序降级。
- Schema验收通过后，独立 WBS 实现同事务 PlanVersion CREATE/完整快照写入、来源锁定/重查、幂等/Audit及实际 PostgreSQL 端到端；不将 Migration PASS 等同 API/Pilot PASS。

## 剩余风险

冻结候选没有给每个新增字段规定物理子表、确切枚举或 OutputArtifact 生命周期。每个 schema slice 实施前仍须将本 CR 映射到精确列/FK/约束及可回滚迁移；遇到无法从 DM/API/已批准实体事实推出的语义时，先采用明确失败关闭边界并记录，不得编造用户承诺。正式信任、客户确认、UAT、Gate 3～7、Pilot 和三平台发行均保持原状态。

首批精确映射（包含WBS与Plan排除目标表、复合FK目标、业务/文本列映射）由 `docs/progress/plan-02-a04-p04-a04-p03-p04-s01-field-map.md` 记录；OutputArtifact仍保留失败关闭边界。
