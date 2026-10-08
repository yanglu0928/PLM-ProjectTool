# SOL-01-A03-P01：SolutionOutlineVersion 固定引用结构

日期：2026-10-08；结果：`SCHEMA_PASS`，不是完整 `SOL-01-A03` 或正式 Solution Owner PASS。

```text
当前 Phase：Phase 2，依 CR-SEQ-001 前置 Solution 真实 Owner 基础
当前 WBS：SOL-01-A03-P01
输入基线：V2.1 §6.10/Phase 8、冻结 DM-05/SC-01/02/API-04、CR-SOL-002
前置任务：SOL-01-A02 身份 Schema 0136 PASS；现有 RequirementVersion/Review/Project FK 基础
涉及模块：solution ORM/迁移；既有 Requirement/Review/User/Project 仅外键引用
涉及实体：SolutionOutlineVersion、ordered Section identity refs、RequirementVersion refs
涉及 API：无；冻结 SOL_OUTLINE_VERSION_* 不装配
涉及权限：无新公开权限；Owner 未安装时数据库 DML 拒绝
验收标准：同项目/同 Outline 引用、唯一顺序/版本号、指纹与声明形状、空/有数据升降级、历史拒降、回归
风险：不完整的参考来源、DRAFT 被误作 Approved、目录批准代替章节批准、空集合误判覆盖
```

Changed：增加 Schema/ORM 三表、Section 三元唯一和 Outline 批准指针复合 FK；参考方案引用因 SOL-01 尚无实体而不允许写裸 UUID，后续补建。版本计数/指纹实际闭包、来源当前性、内容审查及真实权限均留给后续 Owner，当前所有 Solution 版本写入失败关闭。

Tests：A03-P01 隔离 PG18.6 空/有数据升级、降级重升、三次 drift、FK/唯一/负例/历史拒降 PASS；A02 既有验证脚本因新增 Section 子表导致原单表 TRUNCATE 被 FK 提前拒绝，改为 CASCADE 后确实验证触发器，复跑 PASS。定向 11 PASS，后端全量 `3263 passed, 3 skipped, 4815 subtests passed`。实例停止清理。未运行实际 API/浏览器/Server2025/性能/UAT 或开发 wheel。

TraceLink：CR-SEQ-001 → A02/CR-SOL-001 → CR-SOL-002 → 0137/本验证 → DEC-20261008-1098 → A03-P02。
