# PRT-01-A09-A07-P01：Version CREATE 并发合同偏差前置

日期：2026-10-08。结论：`PRT_01_A09_A07_P01_VERSION_CREATE_CONCURRENCY_PRECHECK_PASS`。
下一项：`PRT-01-A09-A07-P02` 修复 Owner 并接入 Version/Review 五项 HTTP 合同。

## 已识别偏差

冻结 API-04 将 `PRT_VERSION_CREATE` 定义为 `S,L,C,I,M,A`，因此公开 CREATE 必须消费强
`If-Match`。现有 A06 Create Owner 会对 Prototype Root 加行锁并串行分配 `version_no`，但命令、幂等
指纹及 Repository 均未携带/核对 `expected_lock_version`，创建 DRAFT 后也未推进 Root `lock_version`。
若直接造 Router，HTTP 可以语法上要求 `If-Match`，但无法原子阻止旧 ETag 重放，属于伪并发保护。

## 自主修复方案

- 不修改冻结 Operation、路径或控制位；给内部 `CreatePrototypeVersion` 增加
  `expected_lock_version`，纳入请求幂等指纹。
- Repository 在已锁 Prototype Root 后精确比对 expected；首次创建在同一事务写 Version/owned set/
  Result/Audit/receipt 并令 Root `lock_version + 1`。版本冲突整体回滚。
- 同幂等键重放优先恢复首次结果，但 expected 已纳入指纹；异 expected/载荷返回幂等冲突，
  不重复推进 Root。HTTP 201 返回首次推进后的强 ETag。

## 影响与回滚

这是对冻结合同的符合性修复，不是 API Breaking Change；当前公开 Prototype Version Router 尚未存在。
无 Migration、依赖、Secret、客户数据或外发。未产生 Version 时可撤回命令参数；一旦生成新 DRAFT，
不允许回写 Root 版本或删除历史，只能前向修复。
