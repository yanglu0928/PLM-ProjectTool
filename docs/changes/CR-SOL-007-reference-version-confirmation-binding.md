# CR-SOL-007：ReferenceVersion 固定来源指纹与 GLOBAL 人工确认绑定

日期：2026-10-08；状态：0143 Schema/ORM 实施并以隔离 PG 验证；受控 Owner/HTTP/实际人工确认未完成。依 CR-EXEC-001 持续授权先登记后实施。TraceLink：Gate 2 冻结 DM-05/API-04（原提交 `64cdf09`）→ CR-SOL-004/005/006 → SOL-01-A04-P03。原冻结内容不改写。

## 冲突和证据

Schema0139 的 `sol_reference_versions.content_fingerprint` 是版本内容摘要；CR-SOL-006 的确认记录 `source_fingerprint` 是固定 DocumentVersion/Evidence 及适用性/类别的规范化来源集合摘要。两者不同，不能仅凭版本内容摘要、脱敏分类字符串或无约束确认 UUID 声称 GLOBAL 来源已经人手核查。0139 的四张 Reference 表写入口仍关闭，已有 0140～0142 确认记录/受权 Proof，但 ReferenceVersion 无独立来源指纹与确认外键。

## 方案比较与选择

- 不选复用版本 `content_fingerprint`：混淆正文与来源，来源变化无法被精确绑定。
- 不选仅保存裸 `confirmation_id`：外键只能证明确认存在，不能证明指向同一组来源。
- 选择在 ReferenceVersion 增 32 字节 `source_fingerprint` 和仅 GLOBAL 非空的 `deidentification_confirmation_id`；确认账本增 `(confirmation_id, source_fingerprint)` 唯一键，版本以复合 FK 固定对应关系。后续 Owner 还必须在当前事务重验管理员/来源/确认未过期或撤销，Schema 不能替代动态 Proof。PROJECT 版本确认 ID 必须为空，但仍保留来源指纹供追溯。

## 差异、风险、迁移/回滚和验证计划

相对冻结 DM-05 是实现来源核查不变量的辅助字段/约束，不改首版 Scope、License 或冻结 `/api/v1`。迁移0143 只增列/约束，不生成确认、不修改现有内容；因旧 ReferenceVersion 无法可靠重建来源指纹，若表中已有行则明确拒绝升级，要求另行人工数据核查迁移，绝不填造指纹。其他有数据业务表必须可无损升级。降级前若 ReferenceVersion 已有行则拒绝丢弃绑定；空表可降至0142并重升，确认账本既有行保留。0139 写入口继续关闭，本 CR 不单独开放业务创建。

验证：ORM/Alembic drift、空库及其他业务有数据升级、有 ReferenceVersion 历史拒升、空表降级重升；正确 GLOBAL/PROJECT、错指纹/错确认/NULL/跨 Scope/不可变历史负例；后端全量回归。未完成 Owner/HTTP/UI/真实人工确认前不得标记 ReferenceSolution 可用或 Gate3 PASS。

2026-10-08 P03-P01：0143 增 ORM/列、确认 `(ID, source_fingerprint)` 唯一键与版本复合 FK；隔离 PG18.6 正确 GLOBAL/PROJECT 和错来源/缺确认/错误 Scope/长度拒绝、已有 ReferenceVersion 拒升且行保留、空表降级重升与 drift PASS。离线 SQL 另发出数据库执行时历史保护 DO 守卫，避免跳过该安全约束；全量后端3298通过/3跳过/4824子例。0139 Reference 四表 Owner 仍拒写；验证脚本为合成测试行，不构成正式业务版本。
