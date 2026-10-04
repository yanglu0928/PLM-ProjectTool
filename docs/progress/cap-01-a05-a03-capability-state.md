# CAP-01-A05-A03：Capability 状态与元数据 Owner

日期：2026-10-05。结论：`CAP_01_A05_A03_STATE_OWNER_PASS`。下一项：`CAP-01-A05-A04` 六个普通命令HTTP与默认关闭组合。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A03
输入基线：冻结DM-05/API-04、Schema0094、CR-CAP-001/002、DEC-840/841
前置任务：Capability创建/验证/Review正式化和当前受权读取已通过
涉及模块：capability application/infrastructure；Schema0095；Audit/Idempotency
涉及实体：CapabilityBaseline、BaselineVersion、正式指针、AuditEvent、IdempotencyReceipt
涉及API：本项不挂HTTP；实现CAP_BASELINE_PATCH/ARCHIVE与CAP_VERSION_RESTRICT内部Owner
涉及权限：当前Session/CSRF/DeploymentAdmin与License双阶段重验
验收标准：强ETag元数据、归档终态、受控单向限制、正式指针原子清除、Review栅栏、重放/Audit/回滚/拒降
风险：限制后仍可正式引用、评审中途改状态、归档重放漂移、任意原因文本、守卫过宽
```

## 变更与实现

按CR-CAP-002追加Schema0095，不改写0094、不增加Root或字段。数据库只开放三类新形态：ACTIVE Baseline的名称/说明更新、ACTIVE→ARCHIVED，以及DRAFT/APPROVED/RETURNED/SUPERSEDED→RESTRICTED。延迟完整性现精确要求APPROVED数量与正式指针一致；限制当前APPROVED时Version状态、指针清空和Baseline锁推进必须同事务。IN_REVIEW必须先由既有Review Owner撤回/退回，不能直接限制或归档。

内部Service先验证Session/CSRF，再检查License，写事务中重新验证DeploymentAdmin。Patch规范化名称/说明、强ETag且拒绝无变化写；Archive和Restrict使用部署级持久幂等收据并只写一次Audit；限制原因仅接受64字符内大写受控代码并保存在不可变AuditEvent。所有命令按Baseline→Version固定锁序执行。

ARCHIVED收敛为Baseline终态写栅栏：不撤销既有项目精确引用，但禁止后续元数据、新Version和Version状态写入。这样Archive首次响应的ETag可长期精确重放；需要限制的Version必须先限制再归档。当前正式版被限制后，ACTIVE Baseline允许暂时无正式指针，普通成员按A02策略看不到该基线，直到新Version评审通过。

## 验证

- Windows 11 / PostgreSQL 18.6全新隔离库：空库`0095 -> 0093 -> 0095`、两次drift；四版本Review历史基础上完成Patch v12→v13、新Draft/IN_REVIEW期间Restrict与Archive拒绝、撤回、当前APPROVED限制并清空指针、另一RETURNED限制、两命令精确重放、Archive v18→v19、归档后Version写拒绝、三类Audit计数和历史拒降。A02管理员/成员读取回归在0095 head通过；临时库清理。
- 新增7项单元测试（6个Service、1个Schema），后端全量2579项通过、3项既有条件跳过。首次全量仅因迁移合同仍固定0094而失败，更新为0095后完整重跑通过。
- 开发wheel内Capability 43项通过；Migration 4项需将wheel解包为正常包目录后通过。直接把zip格式wheel路径作为`PYTHONPATH`时，迁移脚本的文件目录读取3项失败，该方式证据作废，不是产品失败。最终wheel SHA-256 `f1e4b6f006357b8fa0afb773d2941abc70aa5e299318cca6af86e048ccc7bdb0`。
- 首轮实库产品链已正确拒绝归档后建版，但夹具误期待旧错误码；修正断言后从新库重跑通过。`compileall`与`git diff --check`通过。

## 兼容、迁移、回滚与剩余边界

内部Schema`0094 -> 0095`仅替换守卫/完整性函数，无冻结URL/字段、依赖、网络、Secret、外发或客户数据变化。无A03历史可恢复0094；存在PATCH/ARCHIVE/RESTRICT Audit、ARCHIVED或RESTRICTED历史拒降，停止新命令并向前修复。

三个命令尚未挂HTTP；Baseline/Version Create、Validate的统一传输合同、默认关闭组合、正式信任、前端、Server2025、性能及Gate 3/发行仍未完成。
