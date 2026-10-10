# HND-01-A04-A02-P01：Handover Review Schema0101

日期：2026-10-05。结论：`HND_01_A04_A02_P01_REVIEW_SCHEMA_PASS`。下一项：`HND-01-A04-A02-P02` Handover Subject Owner 与 Review 内部链。

## 编码前检查与拆分

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-01-A04-A02-P01
输入基线：冻结DM-05/API-02、Schema0034/0035/0097/0100、CR-HND-001/002
前置任务：Handover Draft/Validate、Action Schema/生命周期/读取均已通过
涉及模块：handover、review、project
涉及实体：HND-01/HND-02、RVW-01/RVW-02、HND-03
涉及API：本项不开放HTTP，不改变冻结Operation
涉及权限：本项只建立数据库终态边界，应用权限留P02
验收标准：PROJECT Subject绑定、Action覆盖、受控状态转换、正式指针与Item投影同事务
风险：Review与业务状态半提交；缺资料未承接即送审；退回/撤回误写正式事实；历史降级丢失约束
```

原 `HND-01-A04-A02` 同时包含数据库状态转换边界和应用层 Subject Owner，回滚范围不同。为保持一个WBS只解决一个明确问题，将其拆为P01 Schema0101、P02内部Review链，之后再分别实现HTTP、Windows组合与UI；不改变冻结Operation、Review语义或CR-HND-002范围。

## 实施结果

- 新增Schema0101，只开放 `DRAFT -> IN_REVIEW -> APPROVED/RETURNED`、旧正式版 `APPROVED -> SUPERSEDED`、Item `CANDIDATE -> CONFIRMED` 以及Root正式指针/锁的受控更新，其他Version内容继续不可变。
- 送审提交期延迟校验真实`PROJECT` Review、`HND-02` Subject、Project/Analysis/Version/Round一一绑定；所有Item仍须为`CANDIDATE`。
- `source_missing`或`NEED_CONFIRM` Item送审前必须存在同Version、同Item且非`CANCELLED`的`ANALYSIS_ITEM` Action；Action承接不等于Item确认或问题关闭。
- 批准必须在同一事务完成Review批准、Version批准、所有Item确认和Root正式指针；退回/撤回保持Item候选且不得指向该Version；旧正式版只有在存在更高版本当前批准指针时才能`SUPERSEDED`。
- 离线降级失败关闭；一旦存在Review、正式化或Item确认历史即拒绝降至0100，无历史库可安全恢复Schema0097 Owner守卫。

## 验证证据与偏差

- Windows 11/PostgreSQL 18.6临时库完成空库升降重升、既有DRAFT数据升级、`alembic check`、PROJECT绑定、Action覆盖拒绝、合法送审、提前确认拒绝、批准原子投影与保留历史拒降；标记`HND_01_A04_A02_P01_REVIEW_SCHEMA_PASS`。
- 迁移专项7项通过；后端全量2662项通过、3项既有条件跳过。
- 开发wheel构建并解包导入Schema0101通过，SHA-256 `149a4c6e2b2d92fc07302346d9e2f43178e85ee9ad14ef6caa02c8d02058c046`。
- 首次全量回归的唯一失败是迁移合同仍断言旧head `0100`；同步断言到实际新head `0101`后，专项与全量均完整重跑通过。未放宽产品Schema或跳过失败用例。

## 兼容、升级与回滚

内部Schema从0100增量到0101，仅替换/新增数据库函数和延迟约束触发器；无表列、冻结API、依赖、网络、Secret或数据外发变化。无Review历史时可降级并恢复0097守卫；已有正式历史时只能向前修复。P01不创建Review、不开放业务写入，P02完成前生产Owner仍失败关闭。

后续P02真实Version插入链发现共享INSERT触发器存在跨表字段解析缺陷；`CR-HND-004`已修正并在全新库重跑本验证。原P01 wheel `149a4c6e...58c046`仅保留为历史构建记录，不再作为候选包；修正版随P02 wheel及其新哈希继续。
