# SOL-01-A04-P02-P03-P03-P02：GLOBAL 人工确认受控撤回

日期：2026-10-08；结果：`DEIDENTIFICATION_REVOKE_INTERNAL_PG_PASS`，P03-P03 整体未完成。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P02-P03-P03-P02
输入基线：冻结 DM-05/API-04、CR-SOL-006、Schema0140/0141
前置：内部人工确认命令、读取 Proof 与 0141 历史保护已完成
涉及模块/实体：Solution 确认账本、撤回 Application Service/Repository
API/权限：无公开 API；要求当前 DeploymentAdmin Session/CSRF/License
验收：一次性撤回、不可改其他列、同事务 Audit/收据/回滚、Proof 拒绝、迁移上下行
风险：PG 中管理员/来源为合成 Port；实际人工确认和真实 HTTP/文件链未验
```

0142 对已存在的 `revoked_at` ORM 字段只改变触发器 Owner：确认行不得生来已撤回；仅允许一次空值→时间戳更新；其他字段/二次撤回/删除/截断继续拒绝。降回 0141 仍保留已撤回时间和读取拒绝，不做数据清除。撤回命令先后重验当前管理员和 License，再锁行、检查来源最新行、固定原因码与收据；撤回时间、Audit 与收据同事务。回放只返回原时间，不写第二次 Audit。

验证：Win11 隔离 PG18.6 从空/既有数据升级0142、降至0141/重升、Alembic drift、历史拒改/拒删/拒截断；合成确认→撤回→读取拒绝、审计失败事务回滚、同 Key 重放/异 Key 重撤拒绝；后端单元 3298 passed、3 skipped、4824 subtests passed。独立脚本退出0并清理临时 PG。API、前端、真实用户确认、Auth+Document+Evidence+文件组合及 ReferenceVersion 正式绑定未验证。TraceLink：CR-SOL-006 → DEC-20261008-1107 → Migration0142/内部命令 → 隔离 PG 证据 → 后续完整组合。
