# SUR-02-A03：PROJECT_RECORD 固定来源证明与 Round append Port

日期：2026-10-06。结论：`SUR_02_A03_ROUND_SOURCE_PASS`。下一项：`SUR-02-A04` Round create/list/get、稳定 cursor、授权/Audit/持久幂等与隔离验证。

## 实现

- Evidence Owner 增加向后兼容的可选角色集与精确 Document category 策略；默认仍仅 ProjectManager 且保持原 Workflow 非 TEMPLATE 语义。Survey 组合要求 ProjectManager/ImplementationMember 与精确 `PROJECT_RECORD`。
- 新增 Survey-owned 最小 proof adapter，只传递 Evidence、Document/Version、观测 lock/fingerprint 和受权记录人；不复制正文、locator、路径或文件内容。
- 新增 caller-transaction Round source append Repository：锁定 OPEN Round，固定可空 Question 到该 Round 的 SurveyVersion，在 Round 锁内分配连续 ordinal，写入后不 commit。数据库触发器再次重验 Evidence 当前事实。

## 验证

- Windows 11 / PostgreSQL 18.6：真实 Evidence 行 proof、ImplementationMember 允许、CustomerManager 拒绝、精确 PROJECT_RECORD、固定 Question、两次连续追加、错误 Question 回滚、Evidence/Round 行锁持续到调用方提交、CLOSED 后拒绝及 Alembic drift 均通过。
- 定向 11 项/9 子断言；后端全量 `2864 passed / 3 skipped`、`4077` 子断言，两个既有依赖弃用 warning 保留。
- 开发 wheel `1063` 项并包含 proof/append 模块；SHA-256 `72ca80f5920f95e02da2dfc4dc2be89381c15cc4f53a02fc70eb0a5d1a81ecb3`，不是可交付安装包。

## 兼容与回滚

无 Schema/Migration、公开 API、角色枚举、依赖、Secret、网络或外发变化。现有 Evidence Owner 构造未传新策略时行为不变；停止后续组合并移除两个 Survey 内部模块即可阻止新追加，0107历史保留。A04 才建立完整受权命令、Audit、幂等和公共读取。
