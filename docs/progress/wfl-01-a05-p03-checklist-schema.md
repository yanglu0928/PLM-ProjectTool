# WFL-01-A05-P03 Checklist owned 记录两表

日期 2026-09-26；0.1.0.dev0；CR-WFL-004；结果 WINDOWS_ISOLATED_SCHEMA_PASS。真实授权/Owner/Gate/写命令仍未完成。

## 编码前检查与实施

Phase 2；输入 DM-02/SC-01 WFL-01/API-02、CR-WFL-004 及已验证不可变快照。范围为 `wfl_checklist_records`、`wfl_checklist_record_refs` 的 ORM、独立自包含 `20260926_0032` 和真实数据库结构验收。无新 API/权限策略/外部依赖/架构变化，原 0030/0031 不修改。

根保存首次/更正、Item 与 Workflow 两个版本序列、supersedes 同 Item/项目复合 FK、actor/trace/UTC/内容摘要/理由影响；引用为 typed/Scope/观测版本与状态/摘要/时间，EVIDENCE generated identity 连接真实 FK。数据库强制 created_xid 与 observed_stage_state，拒绝当前阶段/归属/版本不匹配、缺可信旧记录和事后补写引用。提交时核对两个当前投影、Stage 状态保持不变、正向完整依据和 Evidence 当前观测一致性。

FAIL 可记录不足，不造意见；有依据时仍要求真实 Evidence 身份和项目/观测一致，允许 INELIGIBLE Evidence 与合成 RETURNED Review 状态。PASS/WAIVED 只接受 ELIGIBLE/APPROVED 必要集合；WAIVED 另需完整例外/理由/影响。Review/批准例外只有结构白名单和历史字段，目标 Schema/Owner 尚缺，不把插入成功当实际批准。普通应用不能 UPDATE/DELETE/TRUNCATE（含 CASCADE）或在提交后补 child。

一个记录事务只处理一个 Item，Workflow 锁+1但不移动阶段；BLOCKED 更正保持 BLOCKED，不隐式恢复。只要存在新记录，必须其根/refs/当前 Item 和 Workflow 一起提交。对既有当前表直接 SQL 的结构路径未在本任务全面加历史强制触发器；未来受权命令/Gate 必须解析可信完整链，写路由仍关闭，不能把旧裸 SQL 的 PASS 当业务证明。

## 实际验收

Windows 11/Python 3.13/PostgreSQL 18.6；`validation/wfl-01-a05-p03-checklist-schema/verify.py` 随机隔离库 PASS，清理仅脚本创建的库。

- 空库 head up、空历史 down 至 0031、re-up；有既有初态与合成旧 PASS/无链的升级/down/re-up 状态原样不变、不自动造记录；ORM metadata check 无新增操作。
- 首次 FAIL 可无依据，PASS/WAIVED 完整集合；九种受控更正组合实际提交，旧记录保留，旧父/缺父/跨 Item/项目/未知链拒绝；初态与已有非初态无链不伪造新父。
- 两同时 expected version 请求仅一个成功，另一个明确 current facts mismatch；不是把任意数据库故障算并发保护。根/引用/Workflow/Item/Stage/Evidence 快照用于拒绝后回滚核对。
- 缺 Item/Workflow 更新、缺正向 Evidence/Review/例外、重复 refs、非法状态/版本/阶段/actor/理由/Hash/Scope/跨项目/失效观测、提交前 Evidence 变化拒绝。合成 Audit Port 故障在写后回滚；未调用正式 Audit 应用服务，不声称完整审计命令已验收。
- BLOCKED 记录不自动恢复，尝试在记录事务隐藏恢复被拒；允许 GLOBAL Evidence；Evidence 后续 INELIGIBLE 不改历史，新的 PASS 被拒，新的 FAIL 可记录不足；RETURNED 合成 Review 可作 FAIL 观测，不能作 PASS 依据。
- UPDATE/DELETE/TRUNCATE CASCADE、提交后补引用、非空 down 明确拒绝；失败降级后 head 保持 0032、历史数量不变。
- Alembic generated default 不可修改提示保留，额外验证 evidence_id 是 ALWAYS generated，真实 EVIDENCE/其他种类行的生成值分别符合 ref_id/空；不以提示或 metadata check 单独证明表达式。

首轮拒绝测试发现 C 区域设置下 PostgreSQL 普通空白字符类漏判中文全角空格，已在 ORM/0032 使用显式 Unicode 空白字符集合修复，并重跑拒绝/合法矩阵通过。不依赖操作系统区域设置来接受空理由/影响。

后端 663 项无失败（新增 3 项 metadata/迁移契约测试，2 项既有符号链接环境跳过）；0031 历史 Schema、0030 实例 Schema、受权初始化/查询/Windows 两模式 HTTP 关联脚本回归 PASS。旧历史脚本的失败 downgrade 后 head 断言更新为实际 0032，原迁移内容保留。

开发 wheel 构建并核对包含 ORM/0032 PASS；SHA-256 `76cdc3821f2d3e6daaaf5da4ba137488b56c07f44918eaea6fef56afb2f7e605`。未测覆盖率/性能，wheel 不是正式安装包。

## 兼容、升级、回滚与后续

升级前备份并 Alembic 至 0032；不改变旧投影/历史，无 Schema 以外依赖或 Breaking API。记录/refs 非空拒绝破坏性 down；可不装配服务并保留历史。旧非初态无链须可追溯修复，不自动回填。

当前没有公开 Checklist 写路由/应用命令、实际 Review/例外/业务 Owner/Gate evaluator 或 GateItem 固定记录 FK。Server 2025 未运行，Debian 13 暂不验证，Gate 3/正式发行未通过，原业务 Scope 保留。

Next：WFL-01-A05-P04 受控事务当前记录查询/固定依据快照（拒绝无链/过时记录），再独立补 Gate→记录关联与实际授权/Owner 命令。不把结构记录当用户确认。
