# SOL-06-A14-P09：结构化专项送审 Windows 11 Edge 真实闭环

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_SUBMIT_WINDOWS_BROWSER_PASS`；证明受控 Windows 11 内部链可用，不表示专项已批准、Gate 3、Pilot 或正式发行已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P09`|
|输入基线|冻结 `SOL_SPEC_VALIDATE`、`SOL_SPEC_SUBMIT_REVIEW`、CR-SOL-021、A14-P07 Windows 显式写组合、A14-P08 前端安全动作|
|前置任务|后端 Review/状态/Trace/来源原子闭环、生产 Router 装配、前端全量/typecheck/build 已通过|
|涉及范围|一次性验收夹具；不修改产品代码、Schema、Migration、冻结 API、权限、License 或依赖|
|验收标准|实际 Edge 加载生产 Vue，经生产 FastAPI/Uvicorn 与 PostgreSQL 18.6 完成成员隐藏、负责人现时验证、ACTIVE 评审人选择、固定请求送审、201/原 Key 重放、跨项目清屏和唯一数据库事实|
|风险|页面未完成加载即取证；未知写结果换 Key；浏览器夹具污染上游身份；只看页面而未核数据库|

## 实施与证据

- 使用 Windows 11 已安装 Microsoft Edge `155.0.4283.62`、Vite 生产构建、生产 FastAPI/Uvicorn 组合及每轮全新可弃 PostgreSQL `18.6`。全部流量限定 `127.0.0.1`，账号、项目、正文和数据库均为合成一次性材料；未外发客户数据。
- ImplementationMember 实际登录后只能看到“仅当前项目负责人可送审”，页面不存在送审按钮。一次性 ProjectManager 登录后，必须先点击“验证当前事实”并取得与固定详情完全一致的 `ready_for_review=true` 报告，才能选择当前 ACTIVE 评审人。
- 浏览器在发送前保存 actor/project/spec/series/reviewer/Key 的精确待发记录；模拟结果未知并离页返回后，页面禁止更换评审人，只有显式勾选后才按原操作号、原正文重试。
- 首次 UI 请求返回严格 `201`，随后在同一浏览器按相同 Key/正文直接重放仍为 `201`；抓取的两次请求正文、Idempotency-Key 和 CSRF 边界一致。跨项目写为 `404`，跨项目详情不会保留原项目 Review 或成员内容。
- 数据库独立断言固定版本由 `DRAFT` 转为 `IN_REVIEW`，且仅存在一个 Review、一个首轮、一个 START 状态结果、一份平台送审收据和两条对应 Audit；并继续跑完上游来源创建、Trace 与 Review 生命周期回放。
- Edge 最终页面在内存中生成有效 PNG（141726 bytes）后立即丢弃；浏览器临时 profile、可弃数据库和合成凭据随验证清理，不作为仓库成果或正式信任材料。

最终命令以退出码 `0` 完成，并输出：

```text
STRUCTURED_SPEC_SUBMIT_EDGE PASS: Edg/155.0.4283.62; manager-only ready validation, active reviewer, exact pending request, 201/replay, cross-project clear, rendered PNG bytes=141726
SOL_06_A14_P09_SUBMIT_BROWSER_PASS: Win11 Edge production Vue/FastAPI/PG18.6 manager-only current validation, active reviewer, exact pending Key/body, 201/replay, cross-project clear and unique database facts
```

## 偏差与无效尝试

- 当前 Computer Use 会话只暴露内置浏览器，没有可选择的 Edge 表面；因此没有把内置浏览器冒充 Edge，而是通过本机已安装 Edge 的 DevTools 协议完成真实引擎验收。该替代不改变浏览器、产品构建、服务端或数据库验收标准。
- 首轮夹具回调层级少一层、初始凭据版本假设冲突、Review 版本字段查询位置错误，均在进入有效验收前失败并修正，未计作通过证据。
- 两轮浏览器夹具过早读取成员/负责人页面导致时序不稳定；最终等待权限文案或已启用的现时验证动作，而非放宽业务断言。
- 曾尝试轮换既有合成负责人凭据；上游回放正确拒绝旧身份，数据库也正确禁止凭据版本回退。最终改用独立一次性 ProjectManager，完全不修改上游身份。相关失败运行均不计作证据。

## 兼容、升级与回滚

- 本项仅新增显式验收脚本与记录，无产品升级动作。可删除夹具回滚，不影响既有 Review、状态、Audit 和收据；任何正式环境历史不得删除。
- A14 送审实现链已完成，但 201 只代表进入评审，不代表批准、实施完成、客户确认或 UAT。正式公钥/服务账户信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和 Release 状态不变。

Next：`SOL-06-A15-P01` 核对通用 Review 决定/读取、SOL-06 Subject Owner、Windows 组合与现有前端缺口，固定 Reviewer 批准/退回的最小纵向闭环；本前置核查不预先形成批准事实。
