# SOL-06-A15-P03：结构化专项 Review GET 授权与冻结投影

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_GET_CONTRACT_PASS`；仅证明默认关闭的读取边界、内部授权和投影合同，不表示 Windows 生产入口已开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P03`|
|输入基线|冻结 API-02 `REVIEW_GET`、RVW-01-A04/A05、A15-P01/P02、SOL-06 当前 Owner/0165|
|前置状态|Review 固定快照读仓储与内部两层授权服务已存在；缺真实 SOL-06 read owner、独立注册表和 HTTP 投影|
|涉及模块|Review read service/registry/API、SOL-06 Subject read authorization/repository、应用工厂与合同测试|
|涉及 API / Schema / 权限|细化既有冻结 GET；复用 `REVIEW_GET` 四类成员策略与 License；无 Migration、角色或权益变化|
|验收标准|默认 404；Host/Session/License/Project/Owner 分层；系列与固定版本分别证明；活动轮、Assignment/Decision/ETag 严格投影；无内部证据泄露|
|风险|把写 Owner 自动当读 Owner；旧审批替代当前成员；历史版本越过系列；终态轮误报活动；主题正文或内部锁泄露|

## 实施结果

- 新增独立 `ProjectReviewSubjectReadRegistry`，只验证 `SUBJECT_TYPE + authorize_read`，没有扩大既有写生命周期 Owner 的强制接口或权限。
- SOL-06 读取 Owner 在调用方同一事务中重新确认当前 Project member；系列身份与固定 `structured_solution_spec_id` 分别使用窄共享读锁证明。未知、跨项目、成员失效或错误版本统一隐藏。
- 内部 `ReviewReadQuery` 增加严格布尔 `include_active_round`；不能与指定历史 `round_id` 混用。HTTP GET 只取当前活动轮，终态 Review 的 `active_round` 为 null，不伪造“最新历史轮”。原有 identity-only 与明确 fixed-round 调用保持兼容。
- 新增默认关闭的 `REVIEW_GET` Router 和精确 DTO：仅 Review/Subject identity、活动轮、Assignment/Decision 及双层 ETag；不返回主题正文、来源、指纹、快照或锁信息。拒绝 query 和非 canonical UUID。

## 验证证据

- 定向单元/合同：`41 passed, 38 subtests passed`，覆盖读写 Registry 分离、SOL-06 当前成员/系列/固定版本授权、identity/active/fixed 服务语义、默认关闭、严格投影和安全错误映射。
- 后端全量：`3757 passed, 3 skipped, 5859 subtests passed`。
- Python 3.13 开发 wheel 共 1416 项，包含 Review read Router/Registry 与 SOL-06 read Owner，SHA-256 `c75c9d923cafc3c3e255721cfb9a5ca9870d97acd37e881d00a246f9c1f7e87d`。该 wheel 不是 Pilot 或正式发行包。

## 偏差、兼容与回滚

- 初次 wheel 核验命令因包含动态递归清理被本机安全策略拒绝，未执行构建或删除；改用明确的系统临时目录且不在命令内递归删除后完成构建。临时 wheel 位于系统 Temp，不属于仓库或交付物。
- 冻结合同只承诺 `active_round`，因此本项没有把“最新终态轮”或 LIST 偷渡进精确 GET；Reviewer 任务发现仍是独立缺口。此选择保留终态 GET 的准确 null 语义并避免未冻结 query。
- 无 Migration、旧数据、冻结 URL/角色、License 或依赖变化；同版升级后仅显式注入才开放。可移除 Router/读注册停止入口，Review 历史不受影响。
- Windows 生产组合、真实 HTTP/PostgreSQL、Reviewer 前端、Edge 决定链、正式信任、Gate 3/Pilot/Release 仍未通过。

Next：`SOL-06-A15-P04` 将 SOL-06 read owner 与 `REVIEW_GET` 装入 Windows 显式读取组合，并以 Windows 11 / PostgreSQL 18.6 验证当前活动轮、终态 null、隔离与 License。
