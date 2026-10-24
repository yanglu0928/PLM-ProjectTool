# CR-HND-006：Handover 送审时限与备注兼容收窄

日期：2026-10-05。状态：已实施并验证。关联 `HND-01-A05-A05`、冻结 API-04 `ReviewSubmissionRequest`、DM-05、Schema0034/0101 与 CR-CAP-003；不改写 Gate 2 原冻结提交 `64cdf09`。

## 偏差

冻结公共 DTO 包含 `reviewer_ids/policy_ref/due_at/submission_note`，但当前 Review/ReviewRound Schema 未定义时限和提交备注的持久字段，Handover 也没有可代替该事实的 Owner 表。在未建模前接收非空值会造成静默丢数据，自行写入其他备注列会产生不可追溯的双事实。

## 方案

- V1 请求仍精确保留四字段，`policy_ref` 固定 `HANDOVER_ALL_V1`。
- `due_at` 和 `submission_note` 当前必须为 `null`；任一非空均返回 `VALIDATION_FAILED`/422，不截断、不改存、不仅写 Audit。
- 若后续确需时限/备注，必须以新 Change Request 同时补数据模型、Migration、安全投影、升降级与历史验收；不追写原冻结提交。

## 影响、迁移、回滚与验证

无 Schema/Migration/依赖/配置/Secret/网络/外发。客户端必须显式发送两个 `null`；非空调度信息不会被受理。回滚方式为停止注入 Handover submit-review Router，合法 Review 历史保留。

验证结果：严格 DTO 合同证明非空值 422；Windows 11 / PostgreSQL 18.6 证明 Review identity/Round/Subject/Audit/幂等收据在单 UOW 原子提交，Audit 故障全回滚，首次回执在 Review 批准后仍可从不可变首轮恢复且重验当前权限。后端全量 2697 项通过、3 项环境条件跳过；开发 wheel SHA-256 `6d368e45c0b15ce1488e3d03cf1f4f23db5b34281b5722ac92a545d8e768e83c`。
