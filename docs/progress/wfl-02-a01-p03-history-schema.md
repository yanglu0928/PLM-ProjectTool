# WFL-02-A01-P03 Transition/Gate 三表 Schema

日期 2026-09-26；0.1.0.dev0；CR-WFL-003；结果 WINDOWS_ISOLATED_SCHEMA_PASS。不是实际 Gate/生产授权或 Workflow 整体完成。

## 编码前检查与实施

Phase 2；输入冻结 DM-02/SC-01 WFL-02/API-02、CR-WFL-001/002/003；前置固定 V1/0030/不可变 Domain 形状与历史设计齐备。仅解决三表持久层结构，无公开 API/权限策略/依赖/架构变化，不调用业务 Owner 或外部服务。

新增 `history_orm.py` 与独立自包含 Migration `20260926_0031`，注册 metadata；原 0030 不修改。三表 `wfl_stage_transitions`、`wfl_transition_gate_items`、`wfl_transition_gate_refs` 使用 UUID/复合 Project 父 FK、固定 V1/相邻 pair、观测状态/版本/指纹、独立 Waiver 字段及真实 Evidence FK。Review/批准例外目标表未具备，不虚构 FK。

数据库强制 root.created_xid，提交后禁止补写子项；UPDATE/DELETE/TRUNCATE（包括 CASCADE 请求）拒绝。提交时要求完整来源阶段两项、固定策略、相应 Evidence/Review/例外、同项目事实；root 插入核对 ACTIVE/from/before，提交核对实例 to/after/来源完成/目标 ACTIVE 和当前 Checklist 结果，拒绝半套成功事务。Evidence 插入时共享锁并比对观测事实，提交时再次核对；后续状态合法变化不追改历史。

上述是结构与原子性保护，不是业务批准。数据库超级用户禁用触发器不在应用权限边界。一次事务只推进一步；Checklist 自身追加历史、START、完成/恢复等仍需独立实现，不能仅凭直接 SQL 的合成 PASS 放行客户流程。

## 实际验收

`validation/wfl-02-a01-p03-history-schema/verify.py` 已在 Windows 11/Python 3.13/PostgreSQL 18.6 随机隔离库执行 PASS，清理仅限脚本创建的库。

- 空库全量 up、空 down 到 0030、再 up；已有 NOT_STARTED 与合成 ACTIVE Workflow 的升级/down/re-up 原样不变，无自动历史；Alembic metadata check 无新增操作。
- 36 阶段组合，只有五组合法相邻成功；五条追加记录/十项/二十一引用（含合成 Waiver）、GLOBAL 标准 Evidence 与当前项目 Evidence。
- 当前实例/版本/actor/指纹/项目、跳级、缺项、重复 item/ref、无 Evidence/Review/例外、畸形 Waiver/策略/Scope/观测版本与状态、跨项目/缺 Evidence、半套状态和提交前 Evidence 改变均拒绝并回滚。
- 同时发起两个相同 expected version 请求，只有一次成功，另一项明确 current facts mismatch；不是将未知数据库错误算并发保护 PASS。
- UPDATE/DELETE/TRUNCATE CASCADE 拒绝、已提交后追加 ref 拒绝；后续 Evidence 撤销，历史仍保留 ELIGIBLE/版本 1。非空 down 明确拒绝，head 仍 0031、五条历史不变。
- Alembic 对 generated default 发出“不可修改”提示。未屏蔽；额外查询证明 evidence_id 为 ALWAYS generated，所有实际 EVIDENCE 行值等于 ref_id，其他类型为空。不以提示或 metadata check 单独证明生成表达式行为。

初次运行发现复用 trigger 在 GateItem 访问无此字段 ref_kind，合法记录被拒；已改为逐表分支，重跑合法与拒绝矩阵通过。验证脚本仅接受预期约束 SQLSTATE，未知程序错误立即失败，避免错误归类 PASS。

关联 0030 实例 Schema、既有项目初始化/只读/两种 Windows 平台 HTTP 验证脚本重跑 PASS。后端 652 项无失败（2 项既有符号链接环境跳过）；新增 3 项历史 metadata/迁移契约测试。未测性能或覆盖率。

开发 wheel 构建并检查包含历史 ORM/0031 PASS；SHA-256 `5c805b0049566fb2408ed53a5a8c3ba62ba6e2f33a01a85a6f0dd3f9af65f01a`。不是正式安装包。

## 升级、回滚与已知问题

升级需备份并运行 Alembic 到 0031，不修改旧状态或伪造历史；任一历史存在时禁止破坏性 down。代码回滚可不装配服务并保留三表。旧 ACTIVE/COMPLETED 缺可信链不自动修补，后续写服务须受控处理。

没有运行写服务/HTTP、真实 Review/批准例外/业务 Owner、完整 Gate evaluator/Checklist 历史、正式信任源/性能/三平台发行。Server 2025 未运行，Debian 13 暂不验证；Gate 3 仍未通过，完整 Scope 未缩减。

下一项 WFL-01-A05-P01：Checklist 每次 PASS/FAIL/WAIVED 的追加历史设计与差异登记；在其实际权限/历史/Gate 前置具备前，Workflow 写路由继续关闭。

同步诊断：本轮 Git 已配置本地 HTTP 代理路径在 schannel/HTTP1.1/OpenSSL 下出现 TLS EOF；仅对单次 Git 请求设置空 http.proxy 后 fetch 成功且远端差异 0/0。采用已验证直连同步，不改全局代理、不关闭 TLS 证书校验。该证据定位本轮路径差异，不宣称所有 GitHub 失败均为同一原因。
