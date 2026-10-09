# SOL-03-A04-P02-P03：目录引用的 Reference 现时来源组合

日期：2026-10-09。结果：`SOL_03_A04_P02_P03_REFERENCE_USE_COMPOSITION_PASS`，仅内部证明链；OutlineVersion Owner/HTTP/UI 未接入，Gate 3 仍 BLOCKED。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P02-P03。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-016；Reference 当前资格账本、Document 固定文件/Parse 结果、Evidence 固定 Locator/指纹内部端口均已验证。
- 单一目标：在同一事务内把 ReferenceRoot/最新人工资格、固定 Document/Evidence 物理现时性、创建时规范来源指纹和 GLOBAL 最新人工脱敏确认合成一个只返回最小摘要的证明。
- 模块/实体/API/权限：Solution 内部 Application/Infrastructure，复用上游 Application Interface；`ReferenceSolutionVersion` 的现有分类/适用性字段加入内部快照，不改 ORM/Schema/公开 API/角色。证明入口只能由未来已授权 Outline Owner 使用，不授予项目用户 GLOBAL 原文读取。
- 验收：PROJECT/GLOBAL 真实隔离 PG18.6 与文件正例、跨项目/旧版/RESTRICTED、Document/Parse 篡改、确认到期、当前根行锁、全量回归；GLOBAL 确认撤回及 Evidence 撤回由既有上游合成夹具验证，Outline Owner 接线后需再测最终写入拒绝。
- 风险：未接业务 Owner 时，证明本身不执行调用者角色判断；不得对外暴露为自由查询。相同事务持锁至未来版本写提交是接线必要条件。

## 实施与验证

创建/修订来源资格与目录使用改为共用 `fingerprint_reference_sources` 唯一规范编码函数，保留原 JSON 字段、排序、UTF-8 与 SHA-256 不变。当前 Reference 快照从同一锁定 Version 加载 `source_project_class`、`deidentification_class` 和 `applicability`，避免重算时借用请求值。`CurrentReferenceSourceAdapter` 逐一调用 Document/Evidence 自有受限证明端口，按固定有序集合重算摘要；`ReferenceUseProofService` 恒时比较存档摘要，并验证 GLOBAL 最新确认 ID/摘要/声明/时间/未撤回。没有原文、Locator、文件路径或管理员 Session 向 Solution/UI 透出。

Win11 两套临时 PG18.6 真实 PROJECT/GLOBAL 来源夹具均退出 0；新组合直接验证跨项目、旧版本、RESTRICTED、Document/Parse 物理篡改、到期时钟、事务期间 Root `FOR UPDATE NOWAIT` 阻塞。既有 GLOBAL 来源夹具验证 Evidence 撤回和确认撤回拒绝，但其回归覆盖的是创建侧证明；最终 Outline 写入拒绝仍需 Owner 接线后再验。定向 10 项/20 子例及后端全量 3429 通过/3 跳过/5229 子例通过，保留既有 2 条告警。

兼容/回滚：无 DB/Migration、公开 API、角色或依赖变化；移除内部来源适配器并保持 Outline 写 Guard 关闭即可回滚，冻结数据与历史不变。下一项 `SOL-03-A04-P03` 建立 OutlineVersion Owner 的授权、现时引用证明、计数/Trace、幂等/Audit 原子写与失败回滚，再开放可选 HTTP/Windows 组合。Gate 3 不据此通过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016 → Reference/Document/Evidence 内部证明 → 本组合 → OutlineVersion Owner → Gate3。
