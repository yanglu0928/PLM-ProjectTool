# SOL-01-A04-P02-P03-P01：GLOBAL Reference 脱敏确认 Schema 0140

日期：2026-10-08；依据冻结 DM-05/API-04、CR-SOL-005/006。原 Gate 2 冻结提交 `64cdf09` 不追写。

`plm.sol_reference_deidentification_confirmations` 为 Solution 自有的 GLOBAL 人工确认记录基础：确认 ID、完整来源集合 SHA-256 指纹、来源项目类别、脱敏类别、适用性 JSON、固定人工声明、实际管理员、确认/失效/撤回时间及 Trace。管理员 FK、长度、类型、声明与有限时间顺序由数据库约束。它不是 AI 建议、分类字段或 Audit 行的同义物。表的 INSERT/UPDATE/DELETE/TRUNCATE 全部闭锁；当前不存在创建确认的运行入口，也不允许仅凭表存在性判定人工确认。

迁移 0140 从 0139 线性升级，不修改原四表或既有数据；空表可降回 0139，非空历史拒降。Win11 一次性 PG18.6 跑旧 0139/0138 验证、已有数据/空库升级、升降重升、Alembic drift、约束、闭锁与非空拒降均通过；后端全量 `3284 passed, 3 skipped, 4815 subtests passed`。已有 pgvector/生成列反射警告仍存在，本增量未引入新 drift。后续 P03-P02/P03 必须先实现可审计的人手命令及当前授权 Proof，并把确认绑定到 ReferenceVersion；否则 GLOBAL Reference 写入仍关闭。Server2025/发行/UAT 未验证。
