# HND-02-A01：HND-03 ActionItem Schema/ORM

日期：2026-10-05。结论：`HND_02_A01_ACTION_SCHEMA_PASS`。下一项：`HND-02-A02` Action Create Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-02-A01
输入基线：DM-05、SC-01/02、API-04、CR-HND-001/002、Schema0097、DEC-847～852
前置任务：Handover Analysis Draft/Validate与Review前置核查已完成
涉及模块：handover、project、auth、document、evidence、trace
涉及实体：HND-03及response/evidence/state-event owned collections
涉及API：本项不挂HTTP，不改变冻结20个Operation
涉及权限：本项只建物理边界；后续Create Owner限定PM/IM并保存actor/reason
验收标准：ORM/Migration/up-down/drift、初始OPEN事件、候选来源、跨项目与历史拒降
风险：先Review后Action顺序死锁；无事件Root；SUBMITTED被当关闭；生命周期被通用UPDATE绕过
```

## 实施结果

- Schema0098/ORM新增HND-03 Root及三张owned表，固定来源、输入提示、Owner/期限/优先级、响应文档、Evidence用途、resolution Trace和完整状态事件所需字段。
- 初始只开放 OPEN/v0 Root与同事务唯一 seq0事件；人工reason/Actor一致，DRAFT/CANDIDATE或APPROVED/CONFIRMED同项目Item来源可用，HUMAN来源必须显式说明。
- 生命周期Owner尚未安装：UPDATE/DELETE/TRUNCATE、响应/Evidence提前写入及非初始状态全部失败关闭；不生成业务Action、不改变Version/Item。

## 验证与证据

- Windows 11/PostgreSQL 18.6临时库：空库0098降升、drift、候选Item合法来源、初始事件完整性、跨项目来源拒绝、生命周期关闭与有历史拒降通过；临时库已删除。
- 定向15项、后端全量2617项通过，3项按既定环境条件跳过；首轮唯一元数据库存断言已补HND-03四表后完整重跑通过。
- 最终开发wheel解包定向15项通过，SHA-256 `21e6b7380edfb4116b9c72bc670eaff8ce09da14b4badeab9fc1f3b2f7ccf2c0`。

## 兼容、回滚与未关闭项

内部`0097 -> 0098`只追加表与守卫，无公开API、依赖、配置、网络或外发。空历史可降，有历史拒降；应用可不装配后续Owner，合法历史不删除。

Action Create/状态Owner、Review Subject/正式化、HTTP/UI/Workflow、真实资料质量、正式信任、性能及目标平台发行仍待；Schema PASS不代表待办已经生成、提交、验证或关闭。
