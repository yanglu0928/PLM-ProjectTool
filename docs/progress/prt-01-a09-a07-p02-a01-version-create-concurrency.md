# PRT-01-A09-A07-P02-A01：Version CREATE 强并发 Owner 修复

日期：2026-10-08。结论：`PRT_01_A09_A07_P02_A01_VERSION_CREATE_CONCURRENCY_PASS`。
下一项：`PRT-01-A09-A07-P02-A02` Validation 幂等结果持久化。

## 实现

- `CreatePrototypeVersion` 新增 `expected_lock_version`，强类型限定 0～2^63-2，并纳入幂等请求
  指纹；不同 expected 不能伪装成同一请求。
- PostgreSQL Repository 在锁定 ACTIVE Prototype Root 后精确比对 expected；首次成功于同一
  事务条件推进 Root `lock_version + 1`和 `updated_by/updated_at`，再写 DRAFT Version、owned set 及结果。
  任一后续失败均回滚 Root；旧 expected 返回 `CONFLICT_VERSION`。
- 幂等重放仍从既有 receipt/result 恢复首次 DRAFT，不重复进入 Repository，因此不重复推进 Root。

## 验证与后续偏差

- 新增 stale expected 冲突、fresh expected 连续推进、非法 expected 及持久重放不重复推进单元合同；
  定向 12 项、后端全量 3198 项通过、3 项跳过，compileall 与 `git diff --check` 通过。
- 开发 wheel 1224 项，SHA-256
  `ade0a64bda47630b1e24ea6d3811e1cf307a3d8f1e99379f61967cc2b3d8dacc`；真实 PostgreSQL 18 的 HTTP
  组合、冲突回滚和 ETag 恢复仍留 A09-A09 统一验收。

继续对账发现 `PRT_VERSION_VALIDATE` 冻结为 `S,L,C,I,A`，但 A06 Validate Owner 无幂等键、收据和
持久报告，重试会重算并重复写 Audit。已登记 DEC-1057，A02 将先增不可变 ValidationResult 与收据
闭包，再由 A03 开放五项 HTTP。本项无 Migration/依赖/Secret/外发；Schema head 仍 0134。
