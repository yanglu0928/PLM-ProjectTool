# SOL-04-A02：章节创建首次结果闭锁存储

日期：2026-10-09。结果：`SOL_04_A02_SECTION_CREATE_RESULT_SCHEMA_PASS`；仅 Schema/ORM 存储通过，Section INSERT 与公开 CREATE 仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / `SOL-04-A02`。
- 输入基线：冻结 API-04/DM-05、CR-SOL-012、0136/0137/0138/0146 与 SOL-04-A01；前置已满足。
- 模块/实体/API/权限：Solution ORM/Alembic 与隔离 PG 夹具；`SolutionSection` 首次创建结果；不新增公开 API/权限，后续 Owner 才接 `SOL_SECTION_CREATE` PM/实施成员策略。
- 验收标准：新增关闭的快照表；同 Section/Outline/Project FK、key/时间约束、重复拒绝、未装 Owner 时根/结果写入和 TRUNCATE 拒绝；空/有数据升级、降级重升、Schema drift、已有快照拒降；后端全量回归。
- 风险：若提前开放快照或 Section INSERT，会留下无 Owner 写窗口；本迁移不得改写 0146 或删除历史降级。

## 实施与验证

新增 `20261009_0147` 与 ORM 同构的 `sol_section_create_results`，保存 Section/Outline/Project、固定 `section_key`、首次 `created_at`；复合 FK 锁定同一根，Check 保证 key 1..128 且无首尾空白、时间有限。复用现有身份 Guard，为结果表加 INSERT/UPDATE/DELETE 拒绝和 TRUNCATE 拒绝；Section 根仍由 0146 Guard 全拒。未接应用 Owner、Project 新策略、HTTP 或前端。历史数据不覆盖；空快照可降回 0146，有快照拒降，失败后应向前修复而非删历史。

Windows 11 一次性 PG18.6：空库 0146→0147→0146、已有 Project/Outline 升级及降级重升、4 次 `alembic check`、未装 Owner 的根/结果拒写、TRUNCATE 拒绝、临时关闭 Guard 后复合 FK/非法 key/重复键负例、已有快照拒降，脚本退出 0 并清理隔离库。后端全量 `3386 passed, 3 skipped, 5095 subtests passed`；首次全量有两项静态测试仍预期 0146/旧表集合，更新为 0147/新表后定向 7、全量复跑通过。尝试 `python -m build` 与 `pip` 均不可用，开发 wheel 本项未验证；正式发行包仍待。

已知边界：A03 才能同交付单元安装 Owner/最小 INSERT Guard/延迟快照闭合；正式信任源、服务账户、Server2025、20并发、Gate3/UAT/发行未验，Debian13 实机按用户指令暂跳过。TraceLink：CR-SOL-012 → 本 0147/A02 → SOL-04-A03。
