# SOL-06-A04：类型化内容前置设计

- 当前 Phase/WBS：Phase 2 / `SOL-06-A04`。输入基线：冻结 DM-05 StructuredSolutionSpec、SC-01/02 V-PRJ、0161 闭锁 Root、0162 四类闭锁 refs。前置任务 A02/A03 已验证并推送。
- 涉及模块/实体：Solution / StructuredSolutionSpec owned payload；无 API、权限、跨模块写入。验收：四类结构化最小字段、版本归属、存储、原子性、回滚和独立测试边界明确。风险：JSONB 形状并非完整语义证明；OutputArtifact 目标与 Evidence 资格仍缺。
- 决策：DEC-1201 选择唯一类型化 JSONB owned 行 + 四类应用验证合同。数据库复合 FK 对齐 Root 的 Version/Series/Project/Type；Owner 完成前根及 payload 保持闭锁。Root 指纹应覆盖规范化 payload 和有序固定引用，后续 Owner 在单事务计算并核对；不能只记录 JSON 而漏来源。
- 下一项：`SOL-06-A05` 实施闭锁 payload ORM/迁移和独立 PG 验收；随后再拆分四类 validator、引用资格/Artifact 前置、授权创建 Owner、Trace 与 Section 绑定。Pilot/Gate3 不因本设计放行。
