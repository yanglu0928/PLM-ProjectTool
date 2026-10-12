# 0163：闭锁 StructuredSolutionSpec 类型化载荷

- 版本/来源：2026-10-12 / `20261012_0163`；冻结 DM-05/SC-01 → DEC-1201 → 0161 Root/0162 owned refs。只追加迁移，不改旧历史或冻结 Schema V1。
- `plm.sol_spec_payloads` 每个固定 SpecVersion 至多一行，保存 Version/Series/Project/Type、schema_version=1、JSONB 对象、32 字节 payload_fingerprint 与 UTC 时间。四列复合 FK 保证与 Root 类型、项目和版本一致。数据库拒绝空对象/数组、超过 1 MiB 的 JSONB 文本、错误指纹长度或不支持的 schema_version。
- 四类业务完整性不是 JSONB 形状约束能证明的；PROCESS_MODEL、INTERFACE_SPEC、MIGRATION_SPEC、PERMISSION_DESIGN 的语义验证与有序引用/Root 指纹关联须由后续受权 Owner 同事务完成。载荷表 INSERT/UPDATE/DELETE/TRUNCATE 保持闭锁，Root 与 refs 旧闭锁不变；Schema PASS 不代表真实专项可创建。
- 升级/回滚：0162 → 0163 无回填，空库及已有 Project 数据均可升级。载荷表为空可降回 0162 并重升；非空历史拒降，不得清空生产历史。离线降级禁用。
- 验证：Windows 11 可弃 PostgreSQL 18.6 空/已有数据升级、空表回滚、复合 FK/类型/版本/对象/大小/指纹/唯一负例、DML 闭锁、合成非空拒降及 Alembic drift 通过；A02/A03 回归与后端全量结果以进展文档为准。合成行仅测试，不是正式业务事实。
