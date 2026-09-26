# CR-WFL-003：迁移 Gate 快照的可查询依据历史

日期 2026-09-26；WBS WFL-02-A01-P02；状态 DESIGN_RECORDED / IMPLEMENTATION_PENDING。
授权：用户持续自主执行规则 V1.1；原冻结 `64cdf09`、CR-WFL-001/002 及所有既有 Migration 不覆盖。

## 证据与冲突

冻结 DM-02 要求 StageTransition 追加不可变、GateSnapshot 只引用证据/Review/明确例外；SC-01 明确 `wfl_stage_transitions` 与 `wfl_transition_gate_items`，但未展开依据集合的关系映射。API-02 客户端提交 refs 不等于经过验证的快照。

现有 `EvidenceRow`/0027 保存固定 DocumentVersion/定位/内容指纹，同时 eligibility_state 与 lock_version 可变。只存 Evidence UUID 无法还原当时状态；UUID 本身也不证明引用存在、项目归属或批准。Review ORM/表当前不存在，不能将未实施的 FK 描述成保护已具备。

## 方案比较与采用

- A：仅保存可变当前 Checklist 和 UUID 数组/JSON。没有历史或可查询固定事实，拒绝。
- B（采用）：保留两张冻结表名，另增加 owned `wfl_transition_gate_refs`，按类型保存同事务 Owner 返回的固定引用与当时事实。FK/项目、枚举/版本/摘要使用显式列；不复制客户正文，不把事后当前状态当历史状态。
- Checklist 的 PASS/FAIL/WAIVED 每次记录还须独立追加历史，但不混入本次 Transition 三表实施。其映射需后续独立 CR/Schema；相关公开写路径继续关闭，不能靠本 CR 绕过它。

## 差异与边界

增加一张 owned 引用表及具体列/约束，属于可追溯 Schema 增量；不新增业务 Scope/框架/依赖或修改 `/api/v1`。本 CR 的第一项 Migration 仅支持 `FORWARD` 的五组相邻迁移快照；未实现 START/完成/恢复/退回，这些功能仍在原 Scope，须后续具体设计与实施，不以缩小范围宣称 Workflow 完成。

Owner 查询、真实 Review 和批准例外尚缺，本次结构实施只能以合成事实测试；无生产写服务/HTTP。成功快照不可从请求或 Domain 对象构造成功推定；必须同事务重新授权、证明固定事实并保存 Audit/状态/收据，全部失败回滚。数据库保护不是安全签名，也不是实际 Gate。

## 迁移、回滚与验证

计划 `20260926_0031` 在 0030 后增三表，不修改既有状态、不自动回填历史、不修改既有 Workflow/Project。旧 ACTIVE/COMPLETED 实例来源未知，不编造 Transition；未来写服务须显式拒绝缺少可信历史链的既有实例并走独立可追溯修复，不能静默重置。

升级前备份；空历史允许 down，任何三表历史存在时拒绝 down。应用回滚为不装配相关服务、保留三表，不删除成功事实。数据库测试须包括空库 up/down/re-up、有 NOT_STARTED 和合成 ACTIVE 旧实例升级原样不变、FK/项目隔离/追加保护/完整 Gate 子项与依据提交校验、非空降级拒绝、ORM parity。完整矩阵见设计文件。

风险：多态 Review/例外引用暂没有目标 FK；结构层只防错误类型/漂移/缺项，运行放行依可信 Owner Port，未注册或未实现一律拒绝。后续 Owner Schema 落地时通过独立增量补 FK/历史保护，不修改 0031。具体同事务证明、性能、Server 2025、质量 Gate/正式发行仍待。

Trace：冻结 DM-02 StageTransition → SC-01 WFL-02 → API-02 WORKFLOW_TRANSITION → CR-WFL-001/002 → `docs/workflow/transition-history-design-v1.md` → 后续 ORM/Migration/验证报告。
