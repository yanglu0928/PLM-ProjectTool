# SOL-06-A16-P08：Windows 11 Reviewer Inbox 实际页面闭环

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_INBOX_EDGE_PG_PASS`，仅限 Windows 11 本机合成信任环境。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P08`|
|输入基线|冻结 REVIEW_LIST/GET/DECIDE、CR-RVW-004、A16-P02～P07 与现有 SOL-06 送审、决定闭环|
|前置任务|P06 真实 ASGI/PG、P07 前端合同/typecheck/build 已通过|
|涉及模块|只新增一次性 Windows 11 浏览器验收夹具；不改产品模块|
|涉及实体/API|读取 Review List、Review GET，执行原有 REVIEW_DECIDE；不新增合同或事实类型|
|权限|以当前项目成员和已分配 Reviewer 的真实 Session/Project/Subject Owner 链为准|
|验收|项目入口发现待办、决定后 `my_pending` 消失、`all` 保留终态历史、跨项目清屏、PG 唯一决定事实|
|风险|合成 License/游标密钥不能代表生产信任；浏览器模拟可能掩盖实际服务账户和部署问题|

## 实施与实测

- 新增自拥有的 `serve.py` / `run-edge-browser.mjs` 验收夹具，复用上游结构化专项送审的可弃 PostgreSQL 18.6 环境，在真实 FastAPI/Uvicorn、生产构建 Vue 与 Windows 11 Edge `155.0.4283.62` 中运行。仅使用本机 loopback 和合成业务数据，不发送客户正文或 Secret。
- 负责人在浏览器完成 SOL-06 固定版本送审后，Reviewer 登录并由项目详情入口进入服务端 `my_pending`。页面无需手填 Review UUID 即发现刚送审的任务；进入详情后由已分配 Reviewer 执行 APPROVE。
- 刷新待办后该 Review 不再出现；切换 `all` 仍保留 APPROVED 终态历史。切换另一个项目时原项目列表清屏。验收脚本同时核对浏览器实际 API 响应与 PostgreSQL 中唯一 APPROVE Decision。
- 实际执行输出 `STRUCTURED_SPEC_SUBMIT_EDGE PASS`、`REVIEW_INBOX_EDGE PASS`、`SOL_06_A16_P08_REVIEW_INBOX_BROWSER_PASS`，进程退出码 0；临时数据库和 Edge profile 由夹具清理。脚本语法检查通过。P07 前端全量 `151 files / 1831 passed`、typecheck/build 与 P06 后端全量 `3781 passed / 3 skipped` 已在前序 WBS 完成，本项未重复全量回归。

## 兼容、升级与遗留

- 只增加测试夹具和追溯文档，无产品代码、Migration、API、权限、License、依赖或历史数据变更；无需升级生产环境，可直接撤除夹具。
- 本次 License、Reviewer 账户、游标材料均为隔离合成信任；未证明正式公钥、目标服务账户 Vault/ACL/CA、离线安装/升级、20 并发性能或其他目标平台。Gate 3、Windows 11 Pilot 和正式 Release 仍未通过。Reviewer APPROVE 不等于客户确认或 UAT。

Next：按 `CR-EXEC-002` 审核 Windows 11 Pilot 纵向链与安装关键路径，选择下一独立阻断 WBS。
