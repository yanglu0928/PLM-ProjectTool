# CR-HND-008：Action CLOSE 下游 Trace Owner 缺口与失败关闭组合

日期：2026-10-05。状态：已按持续授权采用兼容方案，真实 CLOSE 正例待 Survey/Requirement Owner。关联 `HND-02-A05-A04`、CR-HND-003、DEC-20261005-883；不改写 Gate 2 原冻结提交 `64cdf09`。

## 偏差

冻结 Action 状态机要求 VERIFIED→CLOSED 必须有同项目 ACTIVE Resolution Trace，且 Trace 两端均由资源 Owner 在当前授权下证明。当前仓库尚无 Survey 或 Requirement 运行模块，也没有 `(survey, SRV-02/SRV-05)`、`(requirement, REQ-03)` 的生产 Trace Target Owner。内部 PoC 曾用合成 Owner 验证 Trace 机制，但合成 Owner 不能进入生产组合。

若为满足七写表面闭环而在组合层直接信任 Trace 行、跳过目标 Owner、把 SUBMITTED/VERIFIED 当 CLOSED，都会破坏冻结 Trace/权限边界；若因此拒绝整个 Action 写组合启动，又会阻断与该缺口无关的 CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL。

## 采用方案

- Windows 写模式装配七个冻结路由及七个真实 Action Owner，六个不依赖下游 Trace Owner 的写操作正常工作。
- CLOSE 始终调用 `TraceResolutionProofService`；当前生产入口使用显式空 Target Owner 注册表，因此存在 Trace 行也会返回 `HANDOVER_ACTION_RESOLUTION_REQUIRED`，不修改 VERIFIED 状态、不写假 Audit/收据。
- 组合工厂保留显式注入 `TraceTargetProofService` 的入口。后续 Survey/Requirement Owner 完成后，只注册真实 Owner 并补真实 Trace 正例验证，不改变冻结 URL、DTO、Action 状态机或已有历史。
- UI 在 Owner 补齐前不得把 CLOSE 显示为可成功能力；SUBMITTED、VERIFIED 继续显示“待验证”“待关闭”。

## 风险、迁移与回滚

风险是当前版本无法客观关闭 Action，Gate/UAT 不能把“全部 Action 已关闭”作为已达成事实；但不会制造假关闭或破坏其他六写。无 Schema/Migration、依赖、Secret、网络或客户数据外发变化。

回滚可撤 Windows Action 写 Router 注入，使七写全部恢复404；合法历史不删除。向前兼容路径是实现并注册真实 Survey/Requirement Trace Owner，然后执行 VERIFIED→CLOSED 正例、跨项目/撤权/失效Trace负例、Audit/收据和并发重放验证。

## 验证计划

1. 组合测试确认七个冻结路由存在，缺依赖拒绝启动。
2. Windows 生产只读模式不得挂写路由，显式写模式才挂载。
3. Win11/PostgreSQL 18 验证 CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL；CLOSE 在无真实Target Owner时稳定422且数据库仍为VERIFIED。
4. 后续 Owner 到位后单独关闭本CR，不用合成Owner冒充生产证据。

实际结果：Win11/PostgreSQL 18生产组合HTTP已完成CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL；另写入同项目ACTIVE Trace后调用CLOSE，稳定返回422，Action保持VERIFIED/v4、Resolution为空且CLOSED Audit为0。替代方案客观通过，但真实CLOSE正例仍未完成，CR保持开放。

2026-10-05浏览器补证：构建Vue通过本机Edge与生产Windows写组合完成CREATE/PATCH/START/SUBMIT/VERIFY/CANCEL，VERIFIED页面的CLOSE按钮明确禁用并显示本CR原因；数据库保持VERIFIED/v4且无CLOSED Audit。该证据证明UI没有绕过缺口，但不关闭本CR。

## 实施中发现的打包偏差

首次 wheel 生产入口导入发现 `plm_assistant.modules.ai.api` 与 `plm_assistant.modules.document.api` 缺少包标记：源码树因 namespace 行为可运行，但 setuptools wheel 未包含对应 API 目录，导致安装包导入 `production_login` 失败。该问题直接阻断可使用程序包，已补最小 `__init__.py`，系统扫描确认其余含 Python 文件的模块目录均有包标记，并要求重新构建、从 wheel 导入生产入口；不改变 AI/Document API 行为或冻结合同。
