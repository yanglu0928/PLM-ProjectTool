# SUR-02-A05：Round 计划与 OPEN/CANCEL 状态 Owner

日期：2026-10-06。结论：`SUR_02_A05_ROUND_STATE_PASS`。下一项：`SUR-03-A01` 核查 SRV-04 Assignment/Response/Answer/Evidence 冻结边界并拆分完整性 Owner；`CLOSE` 继续显式失败关闭。

## 实现

- 新增 PLANNED Round 计划元数据 PATCH：ProjectManager/ImplementationMember 可在强 ETag 下整体替换 UTC 计划起止与受控地点说明；无变化、旧版本或非 PLANNED 状态拒绝。
- 新增 ProjectManager-only OPEN/CANCEL：状态只允许 `PLANNED -> OPEN` 或 `PLANNED -> CANCELLED`，生命周期 actor/time 与 `updated_*` 在同一 SQL statement 中原子一致，lock version 只前进一次。
- OPEN/CANCEL 接入 Session、CSRF、License、项目授权、持久幂等、Audit 与调用方事务；重放读取已提交终态，不重复写状态、Audit 或 receipt。
- 注册冻结角色策略 `SURVEY_ROUND_PATCH/OPEN/CLOSE/CANCEL`。CLOSE 仅保留受权命令位置，当前固定返回 `SURVEY_ROUND_COMPLETENESS_UNAVAILABLE`，不创建 receipt/Audit、不改变 Round；不会以空 Assignment、记录数量或客户端标志冒充完整性。

## 验证与偏差

- Windows 11 / PostgreSQL 18.6：ImplementationMember PATCH、CustomerManager拒绝、ProjectManager同 Key 并发 OPEN、CANCEL/重放、旧 ETag、OPEN/CANCEL终态保护、CSRF/License、Audit故障全回滚与同 Key 恢复、CLOSE零写失败关闭、Alembic drift 均通过。
- 首轮真实库验证暴露 SQLAlchemy `statement_timestamp()` 表达式被 Python `or` 布尔求值，导致 OPEN 在入库前失败关闭；改为显式 `is not None` 分支，保持同一 SQL statement 的 `opened_at/cancelled_at == updated_at`，重新从新数据库完整验证通过。
- 后端全量 `2876 passed / 3 skipped`、`4129` 子断言；开发 wheel `1069` 项，SHA-256 `03ee68e7b1d823bc358cb6b8fee86199dc8edba5f707b45748f5538f8af38ae4`。wheel 不是最终可交付安装包。

## 兼容与回滚

无 Schema/Migration、冻结 URL/JSON、依赖、Secret、网络或数据外发变化；仅增加内部状态 Owner 和四项冻结角色策略。未装配 Router 时外部路径仍 404。可停止后续装配回滚运行入口，已提交的 Round、Audit 和 receipt 历史必须保留。
