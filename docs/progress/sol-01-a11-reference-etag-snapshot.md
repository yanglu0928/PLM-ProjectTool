# SOL-01-A11-P01：Reference Revise 真实锁版本回执修复

日期：2026-10-09。结果：`SOL_01_A11_P01_REFERENCE_ETAG_SNAPSHOT_PG_PASS`；这是 A11 前端施工前置修复，前端尚未完成。

## 编码前检查与偏差

- Phase/WBS：Phase 2 Platform Core / SOL-01-A11-P01。冻结 API-04 的 Revise 与未来 Eligibility 分别推进同一根的锁版本；A08 回执按 `version_no-1` 推导 ETag，仅在 Eligibility 尚未运行时偶然成立。
- 对象/权限：Reference Revise 首次结果、ORM、内部 Owner 与 PROJECT/GLOBAL HTTP 响应；角色、来源资格与路径不变。依 CR-SOL-015 记录后实施，保留已发布 0149/0150 和 Gate2 原冻结提交。
- 验收：0151 空/历史升级、异常历史拒猜、有历史拒降、drift、真实锁版本偏离版本号时的首次/重放同 ETag，旧验证及后端全量回归。
- 风险/回滚：0151 迁移事务内仅回填期间关闭结果表不可变触发器，之后恢复；有结果不可降级，失败只能保持旧版本或向前修复，不能删除业务历史强退。

## 实施与证据

新增 `result_lock_version` 非空结果快照；迁移前拒绝当前根锁历史不满足既有关系的库，合法 0150 历史以其已冻结版本序号回填。插入及延迟闭合检查结果锁版本与根一致。服务返回实际推进后的锁版本，重放读取不可变快照；HTTP ETag 从该快照生成而非推导版本号。`version_no=3` 与 `lock_version=6` 的 Win11 PG18.6 合成真实 ASGI 链返回 `"v6"` 并同键重放一致。

验证：`validation/sol-01-a11-reference-etag-snapshot/verify.py` 通过，含历史升级/异常拒升级/空历史降级再升/有结果拒降/Alembic drift；A06、A07 历史迁移验证通过，Reference API 契约 4 项通过；全量后端 `3376 tests OK, skipped=3`。这些是开发机隔离合成证据，不等于正式目标账户或生产 Eligibility 链的验收。

## 下一步

恢复 A11 受保护前端写桥与严格客户端；响应 ETag/重新 GET ETag 分别代表首次结果/当前根，不能用版本序号换算，也不能把重放 201 当成当前版本。A12～A14 来源选择 UI、Edge/PG，Eligibility Owner，正式目标账户/20 并发/Server2025、Gate3/UAT/可用程序包仍待；Debian13 实机依用户指令暂跳过。
