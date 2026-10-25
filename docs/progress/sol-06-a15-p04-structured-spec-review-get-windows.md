# SOL-06-A15-P04：结构化专项 Review GET Windows 组合

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_GET_WINDOWS_PASS`；证明 Windows 11 生产组合与 PostgreSQL 18.6 真实读取链，不表示 Reviewer 前端或浏览器决定闭环已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P04`|
|输入基线|A15-P03 默认关闭 REVIEW_GET、P02 Windows Review 决定、A14 真实送审链|
|前置状态|Router/内部授权已通过合同但未装入 Windows；真实 Session/Project/SOL-06/Review/PG 读取未验|
|涉及模块|Windows Project Review 组合、生产只读/写入口、组合测试与一次性真实 HTTP/PG 验收|
|涉及 API / Schema / 权限|只装配既有冻结 GET；复用四类 `REVIEW_GET` 成员、License 与 SOL-06 Owner；无 Migration/新角色|
|验收标准|默认应用关闭；只读与写生产模式均挂载 GET；活动轮固定版本、Assignment；终态 null；Session/License/隔离/query；GET 零业务写入|
|风险|只在写模式开放导致 Reviewer 无法读取；读写 Owner 规则漂移；GET 误写 Audit/收据；终态加载旧轮冒充活动|

## 实施结果

- 新增 `create_windows_project_review_read_router`，复用正式 SOL-06 Owner 工厂，但只向独立 `ProjectReviewSubjectReadRegistry` 暴露读取能力；组合真实 Session read access、Project authorization、Review snapshot repository 和 License guard。
- Windows `include_secret_read` 同时用于只读与写平台模式，均显式创建 `review_read_router`；默认/登录专用应用仍不注入。写命令 Router 继续只在 `include_secret_write` 创建，两者权限边界没有合并。
- 生产入口所需 Document 下载/解析依赖必须完整，缺任一项启动失败关闭；读取路径本身只调用 SOL-06 的成员/系列/固定版本窄授权，不运行送审就绪或写生命周期。
- 一次性验证复用真实创建、验证、Trace、送审和终态链，在两个全新可弃 PostgreSQL 18.6 数据库分别覆盖 APPROVE 与 RETURN 前后读取。

## 验证证据

- Windows/生产组合、读取合同与关联服务定向：`71 passed, 26 subtests passed`。
- Windows 11 / PostgreSQL 18.6 两套真实 HTTP 链退出 0：
  - 活动轮：默认 404；匿名/未知 Session 401；query 400；非 canonical UUID 422；跨项目 404；License 403；ProjectManager 与未分配但当前 ACTIVE 的 ImplementationMember 均可按冻结角色矩阵读取同一 SOL-06 Review；固定版本、唯一待办 Assignment、Review `"v1"` 与 Round `"v0"` 一致。
  - 终态：真实通用决定分别推进 APPROVED/RETURNED；随后 GET 返回 Review `"v2"` 且 `active_round=null`，不把历史轮伪装成活动轮。
  - 每段 GET 前后数据库 Audit 总数不变；上游送审/终态、Trace、来源与 ORM drift 回归一并通过。
- 后端全量：`3758 passed, 3 skipped, 5859 subtests passed`。
- Python 3.13 开发 wheel 共 1416 项，包含 Windows Review read 组合与生产入口，SHA-256 `b0749b566c3ce5dc9a3e0529e44b7156fb58dfa09ff22a6a0ac36ceba2259300`。该 wheel 不是 Pilot 或正式发行包。

## 偏差、兼容与回滚

- 实际验证沿用既有可弃数据库链，Alembic 仍输出已知的 pgvector operator-clause 与 computed-default 比较提示；最终 `No new upgrade operations detected`，没有新增 schema drift 或迁移。提示不作为忽略未来迁移差异的依据。
- 无 Schema、旧数据、冻结 URL/字段/角色、License 或依赖变化；后端同版升级即可。关闭 `review_read_router` 可停止读取入口，不删除 Review/SOL-06/Audit/收据历史。
- 当前 GET 是精确 ID 读取，不提供 REVIEW_LIST/任务发现。前端可从刚送审回执进入当前评审，但完整 Reviewer 收件箱仍需后续 LIST 设计，不能在 P05 中伪造。
- Reviewer 前端、Edge 决定链、正式信任、Gate 3、Pilot 与 Release 仍未通过。

Next：`SOL-06-A15-P05` 实现基于已知 Review 回执的安全 Reviewer 页面：先 GET 当前状态/Assignment，再由当前 assigned reviewer 调用冻结决定端点；不以精确 GET 冒充任务列表。
