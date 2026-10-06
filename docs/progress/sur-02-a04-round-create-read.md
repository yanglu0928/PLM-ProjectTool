# SUR-02-A04：Round create/list/get 与稳定读取

日期：2026-10-06。结论：`SUR_02_A04_ROUND_CREATE_READ_PASS`。下一项：`SUR-02-A05` PLANNED schedule PATCH、OPEN、CANCEL 状态 Owner；CLOSE 继续失败关闭。

## 实现

- 新增受权原子 Round 创建：只接受当前 ACTIVE Survey 的当前 APPROVED Version；ProjectManager/ImplementationMember 经 Session、CSRF、License、项目授权、持久幂等、Audit 后创建 PLANNED Round。
- Repository 锁定 Survey 根后为同 Survey 分配连续 `round_no`，防止并发重复；首次结果与 Audit/receipt 同事务提交，重放不产生新历史。
- 新增所有项目成员可用的 Round list/get 内部读取，按 `(created_at, round_id)` 倒序稳定分页；详情返回固定来源的最小 Evidence/DocumentVersion/Question/观测快照，不返回正文或路径。
- 新增独立、会话/项目/页长绑定的 `SurveyRoundCursorCodec`，尚未开放 HTTP。

## 验证与偏差

- Windows 11 / PostgreSQL 18.6：PM/Implementation创建、CustomerManager拒绝、当前批准版本、CSRF/License、同Key并发、冲突Key、Audit故障整笔回滚、Round编号1..4连续、成员两页读取/详情、固定来源投影、跨项目和撤权拒绝、Alembic drift 均通过。
- 首轮验收脚本对同一幂等 Key 每次重新计算计划时间，系统正确返回 `CONFLICT_IDEMPOTENCY`；将合成请求改为相同固定业务载荷后完整重跑通过，未放宽产品规则。
- 后端全量 `2871 passed / 3 skipped`、`4100` 子断言；开发 wheel `1067` 项，SHA-256 `772e2d8ef0f893717d34c21a9bbfe131acadb079917526b15bdd6937dff0ddff`。wheel 不是可交付安装包。

## 兼容与回滚

无 Schema/Migration、已冻结 URL/JSON、依赖、Secret、网络或外发变化；只增加内部命令/读取/游标和三项既有冻结角色策略。未装配 Router 时外部路径仍404。停止后续装配可回滚运行入口，既有 Round/Audit/receipt 历史保留。
