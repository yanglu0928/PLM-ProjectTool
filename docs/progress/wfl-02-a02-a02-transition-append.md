# WFL-02-A02-A02：Stage Transition 原子追加与不可变回读

日期：2026-10-06。结论：`WFL_02_A02_A02_TRANSITION_APPEND_PG_PASS`。
本项关闭 caller-transaction 仓储边界，不代表受权命令、公开 HTTP、完整六阶段流程、Gate 3 或发行通过。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：WFL-02-A02-A02
输入基线：冻结DM-02/SC-01/API-02、六阶段定义V1、CR-WFL-003/004、Schema0031/0033、A01锁序决策
前置任务：Checklist不可变记录/当前查询、Handover两项真实Owner、Stage Transition命令前置核查
涉及模块：workflow application/infrastructure
涉及实体：ProjectWorkflow、Stage、ChecklistItem/Record、StageTransition、GateItem/GateRef
涉及API：无；默认应用及Windows组合均未新增路由
涉及权限：无；调用方必须先完成授权、License和Owner重证
验收标准：调用方事务、精确Gate、原子状态推进、不可变回读、回滚、锁和并发收敛
风险与回滚：不接收历史PASS替代当前证明，不提交事务；删除新增仓储/值对象即可停止新写，既有历史不改写
```

## 实施结果

- 新增严格命令和持久化值对象，目标阶段必须是六阶段V1中来源的紧邻下一阶段，Gate key必须与来源阶段固定清单顺序精确一致；依据至少包含一条Evidence和一条ReviewRound、按类型/UUID规范排序，且观测时间不得晚于迁移发生时间。
- 新增caller-transaction仓储，固定锁定当前Workflow、来源/目标Stage、来源Checklist Item和当前Record，验证ACTIVE、强版本、定义摘要、当前PASS及本次Owner观测与Record typed refs精确一致。
- 原子插入Transition、两个GateItem及全部GateRef，同时把来源Stage置COMPLETED、目标Stage置ACTIVE并将Workflow指针和lock version加一；仓储不commit、不授权、不检查License、不写Audit或幂等收据。
- 成功后从0031/0033历史回读并重算canonical SHA-256，返回原不可变Transition；后续Workflow版本变化不改写原历史。读取按project/transition双身份隔离。
- ApprovedException尚无可信Owner，运行仓储继续拒绝WAIVED；数据库结构的未来表达能力保留。项目真实归档状态仍由下一层受权命令在进入仓储前锁定并证明。
- 没有Schema/Migration、冻结API、依赖、配置、Secret、客户数据或网络外发变化；无需Change Request。回滚为停止调用并移除新增模块，已提交的不可变历史不得删除或改写。

## 客观验证

- 单元测试验证命令Gate顺序/唯一性、Evidence+Review最小依据、canonical摘要对理由和新鲜观测的绑定，以及损坏输入失败关闭。
- Windows 11 / PostgreSQL 18.6隔离全迁移真实库验证：调用方回滚零残留；Evidence当前版本重证后成功；原Record/Refs固定；HANDOVER原子完成、SURVEY原子激活、Workflow `v3 -> v4`；摘要不可变回读；竞争调用仅一方成功，另一方明确`CONFLICT_VERSION`；临时数据库清理通过。
- Alembic autogenerate显示`No new upgrade operations detected`；既有pgvector operator-class和generated-column提示未产生新drift。
- 最终后端全量`2768`项通过、`3`项既有环境条件跳过；定向3项通过。
- 开发wheel共`1011`项，包含三个新增运行模块；SHA-256：`4e96bfc8947398e764e6bfa74fd46372dcb48830ae20db30820b7682369bc395`。

## 后续边界

下一项`WFL-02-A02-A03`实现仅Handover策略的受权命令：先按固定顺序取得两项Owner当前证明，再重验Session/CSRF、ProjectManager、ACTIVE Project和License，在同一UOW调用本仓储，并原子追加Audit与持久幂等收据。HTTP、Windows生产组合、前端及真实浏览器保持后续独立WBS。
