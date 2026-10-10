# SUR-01-A04-A02-P02：Survey Review Subject Owner

日期：2026-10-06。结论：`SUR_01_A04_A02_P02_REVIEW_OWNER_PASS`。下一项：`SUR-01-A04-A02-P03` Review HTTP 合同与生产组合前置。

## 实施结果

- 新增真实 `SRV-02` PROJECT Review Subject Owner 与 PostgreSQL 仓储，固定政策 `SURVEY_ALL_V1`，不创建第二套审批表或状态机。
- 创建只允许 ACTIVE Survey 的最新 DRAFT Version；送审前重验全部当前评审人、不可变内容指纹、题型/条件规则、四类来源与目标部门当前性，然后原子绑定 Review/Round 并转为 IN_REVIEW。
- APPROVE 终态再次重验评审人和全部当前定义事实，原子批准目标 Version、取代旧正式版、更新 Survey 正式指针并写 Audit；RETURN/WITHDRAW 收敛为 RETURNED，保留既有正式指针。撤回不要求已漂移来源重新有效，避免无法继续的 Review 永久锁死。
- 将 Validate 与 Review 的当前事实检查抽为同一个 `SurveyVersionCurrentValidator`，避免两套题型、指纹和来源规则随时间分叉。
- 通用 Review basis 当前只接受 Evidence/Trace，而 Survey 的固定来源是 Handover/Capability/Template/人工记录类型。Owner 不伪造 basis 引用；Review 快照固定 Survey 内容指纹，来源由同一事务持锁和重验。扩展通用 basis 类型必须另走 Change Request。

## 验证证据

- 新增 5 项 Subject Owner 单元测试；与 Validate/Schema 定向合计 15 项通过。
- Windows 11 / PostgreSQL 18.6 全新临时库完成真实 Version 创建、最新 DRAFT 授权、评审人和来源重验、精确开轮绑定、部门来源漂移时批准失败、恢复后批准并正式化，以及第二版来源漂移后撤回且保留首版正式指针；标记 `SUR_01_A04_A02_P02_REVIEW_OWNER_PASS`。
- Alembic head 无新增差异；后端全量 2807 项通过、3 项既有条件跳过。
- 开发 wheel 共 1038 项并包含 Owner/Repository，SHA-256 `10c68d6dbd9f228e71e5b7ad2489fabcb5caa26bb527734b8e1b1f6da1d3f2eb`。

## 升级、回滚与剩余边界

无 Migration、ORM、公开 API、依赖、Secret、网络或数据外发变化。停止后续 Owner 注册可关闭新的 Survey Review 写入；既有 Version、Review 和 Audit 历史必须保留。当前 PostgreSQL 验证直接覆盖 Subject Owner 的持久化与终态合同，尚未装配通用 Review create/start/decide/withdraw HTTP 链；P03/P04 分别完成 HTTP 合同和 Windows 真实组合。Round/Response/Conclusion、Workflow 资格、Gate 3、UAT 与可使用发行包仍未完成。
