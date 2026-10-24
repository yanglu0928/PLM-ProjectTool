# SOL-03-A06-P03-A05-P03-A05：Outline 真实三维 PostgreSQL 验收

日期：2026-10-24。状态：`PARTIAL_FAIL_CLOSED_PASS`；完整三维PASS/缺口/竞态仍待。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A05 |
| 输入基线 | 冻结API-04、A04 Windows组合；Section客户合成终态PG夹具、Requirement当前库存与统一Trace/Review现时Owner |
| 前置 | 一次性PG18.6与合成账户/项目/Section客户批准夹具；真实PG数据须由已有受控Owner产生，禁止直接把测试签名/客户决定当正式事实 |
| 涉及范围 | 验证脚本/记录；若发现产品缺陷，另行记录并修复，不降低覆盖证明标准 |
| 验收标准 | 固定Outline版的order/source/coverage三维在真实Session/PG/Section/Review/Trace/Spec/Requirement来源下完整PASS；移除或撤销一项现时来源后新Key FAIL/UNAVAILABLE且旧Key保持首次观察；跨项目/无权限和已批准状态不被误判；Audit/Receipt原子性与数据库清理 |
| 风险/回滚 | 现有合成Section夹具可能未包含当前需求全链资格；这种情况只能记为前置不足，不能补造PASS或改Owner。脚本在一次性PG运行、完成后清理，不修改现有业务数据 |

正式信任、公钥、服务账户、客户实签、Gate3/Pilot/发行均不由本合成验收替代。

## 当前证据与前置差距

- 复用现有Section客户合成批准夹具后，真实Session/Windows Router/一次性PG18.6创建Outline DRAFT并运行真实三维Owner：`order=PASS`、`source=PASS`、`coverage=UNAVAILABLE`，`ready_for_review=false`。同Key回放保留第一次结果；异Key重新观察，Audit/Receipt各2；跨项目404、错CSRF403；脚本退出0并由上游夹具清理一次性数据库。
- 初始期望完整PASS的两次运行均失败关闭；定位到夹具的Requirement只是用复制角色插入`req_requirements`和`req_requirement_versions`的合成批准外观，未写齐正式需求版本的子项和当前来源。`SqlAlchemyRequirementWorkflowQualificationRepository.lock_complete_scope`返回None，因而库存Owner正确拒绝提供全集。不是可降低的产品条件，也不能把Section的Trace/Review批准外推为Requirement完整资格。
- 后续`SOL-03-A06-P03-A05-P03-A05-P02`需在同一隔离数据库中用现有正式Requirement Owner产生完整需求版本/评审/项目证据，再重跑Outline full PASS、撤销或替换后的新Key缺口、旧Key回放以及并发/竞态。未满足前A05总项不关闭，Pilot/Gate维持未通过。
