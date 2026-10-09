# SOL-01-A06：Reference 修订首次结果闭锁结构

日期：2026-10-09。结果：`SOL_01_A06_REFERENCE_REVISE_RESULT_SCHEMA_PASS`；仅 Schema/ORM 与关闭的 Guard，Reference Revise 根指针 UPDATE/公开 POST 仍不可用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A06。
- 输入基线：Gate 2 API-04/DM-05、CR-SOL-013、0139～0144 Reference 结构/INSERT-only Guard 和 A05 前置；前置满足。
- 模块/实体/API/权限：Solution ORM/Alembic 与隔离 PG 夹具；ReferenceVersion 修订首次结果；无公开 API/权限变化，后续 Owner 才装 PROJECT PM/IM 和 GLOBAL DeploymentAdmin 策略。
- 验收：新增关闭的修订结果表，版本/前驱同根复合 FK、序号/指纹/时间约束；直接插入第 2 版/根指针更新/结果写入/TRUNCATE 拒绝；空库/已有 Reference 升级、降级重升、drift、历史拒降及后端全量。
- 风险：0144 原 INSERT-only Guard 可插入未受控第 2 版；此迁移必须先关闭该路径，不能在 Owner 前暴露根 UPDATE 或结果写入。

## 实施与验证

新增 `20261009_0149` 与 ORM `sol_reference_revise_results`，固定新版本、同根前驱、序号、两个 32 字节指纹与首次时间；复合 FK/Check 约束。结果表独立 Guard 全拒 INSERT/UPDATE/DELETE，TRUNCATE 沿用 Reference 拒绝函数。0144 共用 Guard 在 0149 中仅新增“版本号 >1 拒绝”，不影响初始版本 INSERT；根 UPDATE/DELETE 与来源历史修改继续拒绝。A07 才能把合法修订版本、指针与不可变结果闭合在同事务 Owner/Guard 中开放。

Win11 一次性 PG18.6：空库 0148→0149→0148；已有 PROJECT Reference 两个版本升级、降级重升与四次 `alembic check`；未装 Owner 的第 3 版 INSERT、根指针 UPDATE、结果 INSERT/TRUNCATE 拒绝；临时关闭结果 Guard 后 FK/序号/指纹/重复负例及有结果历史拒降；脚本退出 0，隔离库清理。首轮后端全量两项静态契约仍预期 0148/旧表集合，更新后定向7通过、全量3392通过/3跳过。收紧 Guard 后一轮全量在未修改的 Windows AI Provider 3 秒 ready 等待超时（3391通过/1失败/3跳过，历时27分钟）；该用例定向3通过，随后最终全量重跑 `3392 passed, 3 skipped, 5113 subtests passed`。前一轮失败不计 PASS，长时间调度原因未独立证明。

兼容/升级/回滚：0148→0149 线性迁移，无冻结 API/依赖/前端变化；空结果表可降，已有结果拒降，正式历史须向前修复。0149 down 恢复 0144 INSERT Guard，但不删除旧版本。后续 `SOL-01-A07` 需 Owner 与合法受限 Guard/延迟闭合同单元，PROJECT/GLOBAL 来源资格、幂等/Audit/直接 SQL/真实 PG 必测；HTTP/Windows/UI 与正式账户另验。Gate3/UAT/发行未通过。TraceLink：CR-SOL-013/A05 → 本 0149/A06 → A07。
