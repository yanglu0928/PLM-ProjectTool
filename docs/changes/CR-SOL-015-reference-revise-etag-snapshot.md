# CR-SOL-015：Reference 修订首次结果固定真实锁版本

日期：2026-10-09；状态：`IMPLEMENTED_WIN11_PG_PASS`。按 CR-EXEC-001 持续授权先记录后实施；Gate 2 原冻结提交 `64cdf09` 与既有 0149/0150 历史保留。TraceLink：冻结 API-04 `SOL_REFERENCE_REVISE`/`SOL_REFERENCE_SET_ELIGIBILITY` → CR-SOL-013 → SOL-01-A07～A10 → 本 CR → 0151/A11 前置修复。

## 冲突与选择

A08 的 201 ETag 按 `version_no-1` 推导，A07 的首次结果表只固定版本序号与指纹。首版 Eligibility Owner 尚未开放，所以当下 A07 修订链恰好 `lock_version=version_no-1`；但冻结的独立 `SOL_REFERENCE_SET_ELIGIBILITY` 将来也会修改根锁版本，届时新修订后的真实根 ETag 与版本序号不再等价。重放如果只依赖版本序号，会返回错误预条件，前端可能对后续修订提交过期锁版本。不能静默修改已推送的 0150 或以当前根锁版本重建历史首次响应。

选择新增线性 0151 `sol_reference_revise_results.result_lock_version` 非空字段，保存修订事务推进后的真实根锁版本；结果插入和延迟闭合均校验与当次根一致。应用仓储保存此值，HTTP 首次及同键重放从不可变结果生成 ETag，不从当前根或版本序号推导。前端 A11 只能按响应 ETag/当前 GET ETag 处理，不假定与版本序号相等。

## 兼容、迁移、回滚和验证

0150 历史无 Eligibility 写 Owner，合法既有修订满足 `result_lock_version=version_no-1`。升级先校验当前根 `lock_version` 与其版本序号一致，再对既有首次结果按此事实回填；若不满足则拒升级并逐条审计，不猜测。随后设 NOT NULL/非负约束并更新受限 Guard。空库/有历史升级、空历史降级重升、已有结果拒降、drift、重放与未来“锁版本不等于版本序号”合成负例必测。失败时保留 0150/已存历史并向前修复；不可删除结果强制降级。

差异仅为结果快照与 ETag 正确性，不改冻结路径、角色、Scope、AI 或正式客户确认。0151 无新的外发、购买或生产不可恢复操作。迁移事务内短暂禁用结果表不可变触发器作一次性回填，随即恢复；失败则 PostgreSQL DDL 事务整体回滚。Win11 隔离 PG18.6 空/历史升级、历史异常拒升级、有结果拒降、drift、偏离版本号后的真实 ASGI 201/重放及后端全量 3376 通过/3 跳过已验，详见 `docs/progress/sol-01-a11-reference-etag-snapshot.md`。正式目标账户/20 并发/Server2025/Gate3/UAT 另验；A11 前端可恢复实施。
