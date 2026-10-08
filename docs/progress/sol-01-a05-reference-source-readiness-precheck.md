# SOL-01-A05：Reference 修订/资格来源前置核查

日期：2026-10-09。结果：`SOL_01_A05_REFERENCE_SOURCE_PRECHECK_PASS`；仅静态证据与 Change Request/施工拆分，Revise/Set Eligibility 尚不可用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A05。
- 输入基线：Gate 2 冻结 DM-05/API-04、CR-SOL-004/005/007、0139～0144、SOL-01-A04 创建/读取及 SOL-03-A01 来源阻塞；前置只满足静态核查。
- 模块/实体/API/权限：Solution/Project/Auth/Document/Evidence/Review 只读对账；ReferenceSolution 根、不可变版本和固定来源；`SOL_REFERENCE_REVISE`（PROJECT PM/IM、GLOBAL DeploymentAdmin）与 `SOL_REFERENCE_SET_ELIGIBILITY`（PROJECT PM、GLOBAL DeploymentAdmin）。
- 验收：界定 Guard/Schema/Owner 缺口、来源当前性与人工资格边界，先建立 CR、迁移/回滚及负例计划，拆成单一可验证 WBS；不打开 DML/API 或声称合格来源。
- 风险：把 Reference 创建、历史读取或 DRAFT 版本误当 ELIGIBLE；根 UPDATE 放得过宽；幂等重放从可变当前指针取值；GLOBAL 旧脱敏确认复用。

## 对账与施工拆分

0139 已有 Reference 根资格枚举、当前版本复合 FK、版本 supersedes 同根 FK 与有序 Document/Evidence 固定来源；版本 `version_state` 当前仅允许 `DRAFT`。0144 Guard 只开放 INSERT，根的当前版本指针和资格字段 UPDATE 仍拒绝。现有创建 Owner/GET/LIST/Windows/前端链只证明初次来源的有限可见性，不证明未来修订或资格状态；SOL-03-A01 因缺当前合格 Reference 与 Approved Requirement 仍阻塞。冻结 API-04 仅给操作路径/角色/结果，详细载荷、状态机和不可变首次结果需在后续合同中细化，不可随意放宽。

已先登记 [CR-SOL-013](../changes/CR-SOL-013-reference-revise-owner.md) 与 [CR-SOL-014](../changes/CR-SOL-014-reference-eligibility-owner.md)，保留原冻结提交。后续按以下单问题任务推进：

1. `SOL-01-A06` 修订版本/当前指针的迁移与受限 Guard 详细设计、空/历史库验证；没有安全首次结果与来源闭合前不开放公开写入。
2. `SOL-01-A07` Revise 内部 Owner/资格与持久幂等原子链及真实 PG 负例；再单列 HTTP、Windows 显式组合和 UI/浏览器。
3. `SOL-01-A08` Eligibility 状态机/当前来源证明/人工决定与首次结果迁移设计；再单列 Owner、HTTP、Windows、UI/浏览器。
4. `SOL-03` 恢复前另行证明 Requirement Approved 当前性，并固定只引用 `ELIGIBLE` 的 ReferenceVersion；不能以本核查/CR 代替验收。

兼容/升级/回滚：本项仅文档，无程序、Schema/Migration、依赖或冻结 API 变化；调整施工顺序可回退，历史记录保留。验证：静态核对冻结 DM/API、0139/0144 Migration、ORM、Reference 创建/读与 A04/A21 进度，未运行新测试。TraceLink：Gate 2/API-04 → SOL-01-A04/SOL-04-A21 → SOL-03-A01 → A05/CR-SOL-013/014 → A06～A08。
