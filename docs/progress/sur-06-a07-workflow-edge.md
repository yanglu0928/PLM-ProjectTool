# SUR-06-A07：Windows 11 Edge 前两阶段 Workflow 全链

日期：2026-10-07。结论：`SUR_06_A07_WORKFLOW_EDGE_PASS`。下一项：`REQ-01-A01`
Requirement 运行时前置核查。

## 验收结果

- 隔离 PostgreSQL 18.6 从 NOT_STARTED/v0 初始化；真实 Microsoft Edge 经构建后 Vue 与生产 FastAPI
  顺序完成 START、Handover 两项 PASS、`HANDOVER→SURVEY`、Survey 两项 PASS、
  `SURVEY→REQUIREMENT`，每次写后均独立 GET 刷新，不以首次回执冒充当前状态。
- Edge 收集 22 条 API 响应观察且无 UI alert/运行异常；三张截图视觉 QA 确认 Handover/v3、
  Survey/v6 与最终 Requirement/v7 的阶段、按钮和两项状态均正确，无内部 UUID 暴露。
- 服务端 VERIFY 精确确认 4 条 PASS 记录、2 条 Transition、4 个 Gate item、4 条 Checklist Audit、
  2 条 Transition Audit 与 7 个完成幂等回执；最终状态 REQUIREMENT/v7。临时数据库、凭据、目录和
  Edge profile 全部清理。

## 偏差与证据边界

- SUR-04-A06 的 Survey 夹具拥有真实 APPROVED Conclusion/Review 与实际来源，但它的旧 Handover
  seed 不具备完整 HND-02 正式评审链。为避免复制两套大夹具或直写伪造 Review，本次组合浏览器验收
  只给 Handover 两项注入固定合成资格代理；Survey 两项始终使用真实 current-fact Owner。
- 因此本项证明的是：既有 Handover 真实 Owner/PG/Edge证据与本轮真实 Survey Owner 能在同一生产
  Workflow/UI 顺序组合并正确持久化；不声称本轮重新复验 Handover 私有业务事实。Handover真实性由
  `HND-03-A04`、`WFL-01-A07-P07-A10`、`WFL-02-A02-A07`既有 PASS 承担。
- 该偏差仅存在于 Git 跟踪的隔离 validation harness，不进入产品代码、Schema/API、依赖、License、
  Secret 或客户数据；删除本验证目录即可回滚，产品历史不受影响。

## 验证证据

- Edge：`SUR_06_A07_EDGE_BROWSER_PASS`，22 条 API 观察、3 张截图视觉 QA。
- 数据库/服务：`SUR_06_A07_WORKFLOW_EDGE_PASS`，精确历史与最终 v7 状态通过。
- 清理：`SUR_06_A07_WORKFLOW_EDGE_CLEANUP_PASS`、`SUR_06_A07_OWNED_FIXTURE_CLEANUP_PASS`。
- Python `compileall` 与 Node `--check` 通过。后端产品代码未变化，A06 已完成前端全量 1482 项回归。
