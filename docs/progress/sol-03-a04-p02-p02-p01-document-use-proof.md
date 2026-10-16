# SOL-03-A04-P02-P02-P01：Document 固定来源的内部现时证明

日期：2026-10-09。结果：`SOL_03_A04_P02_P02_P01_DOCUMENT_USE_PROOF_PASS`；仅 DocumentVersion 元数据/物理文件证明，Evidence Locator/解析节点仍待，OutlineVersion 写仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P02-P02-P01。输入：Gate2 DM-05/API-04、CR-SOL-016、DEC-1139、P01 最小合同、P02-P01 当前资格账本。前置：Source Version 已可通过 Reference 账本固定，Document 自有当前版本读取与安全快照存储已存在。
- 单一问题：GLOBAL 合格 Reference 被项目目录使用时，Document 模块如何复核固定 DocumentVersion 仍 AVAILABLE 且物理字节与固定 SHA-256 一致，而不要求项目角色获得 GLOBAL 文档浏览或管理员 Session。
- 涉及模块/实体/API/权限：Document Application/Infrastructure、DocumentRoot/Version/FileObject；无新公开 API、角色策略或数据库表。仅供受权业务 Owner 的内部服务端调用，在同一事务中读锁元数据；不向 UI 输出正文、路径或文件流。
- 验收：PROJECT/GLOBAL 正例、固定版本/Scope/Project/类别、Document/FileObject 状态与摘要一致、物理文件哈希、跨项目/丢文件/篡改拒绝；单元与 Win11 隔离 PG/真实文件正反例。风险：该服务本身不鉴权，因此不能独立挂载公开路由；必须由未来 OutlineVersion Owner 先鉴权并锁定当前合格 Reference 后注入使用。

## 实施与验证

新增 Document 自有 `ReferenceUseDocumentProofService` 和 `SqlAlchemyReferenceUseDocumentSource`。Repository 在调用者事务内共享锁 Document/Version/FileObject，确认 ACTIVE/ARCHIVED 根、AVAILABLE Version、PERSISTENT/AVAILABLE FileObject 以及 Scope/Project、Hash/大小/MIME 一致；Service 对固定版本与允许类别再校验，使用现有 `LocalFileStorage.open_verified_snapshot` 完成路径安全、大小和完整 SHA-256 核验，只返回版本 ID、Scope/Project 与摘要。文件字节、存储定位和管理员会话均不进入返回证明。

定向 4 项/7 子例通过。Win11 两个独立临时 PostgreSQL 18.6 库复用真实 PROJECT/GLOBAL Document/Evidence/私有文件夹具：固定文档、跨项目/错误版本、物理字节篡改失败并恢复；两个脚本退出0。后端全量 3417 通过/3 跳过/5223 子例（2 条既有警告）。无 Migration/公开 API/依赖变化；不接线或撤服务即可回滚，不删除既有文件/版本历史。

下一项 `SOL-03-A04-P02-P02-P02` 由 Evidence 模块完成固定 Evidence 当前资格、Document 关联、Locator/解析节点证明并只返回摘要；再在 Solution 组合两类来源、资格账本与 GLOBAL 确认，验证撤回/到期/并发后才可开放 OutlineVersion Owner。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016/DEC-1139 → P01 合同 → P02-P01 账本 → 本 Document 证明 → Evidence 证明 → OutlineVersion Owner。
