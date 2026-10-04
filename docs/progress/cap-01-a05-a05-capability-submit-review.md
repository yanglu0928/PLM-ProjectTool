# CAP-01-A05-A05：Capability Version 送审外层

日期：2026-10-05。结论：`CAP_01_A05_A05_SUBMIT_REVIEW_PASS`。下一项：`CAP-01-A05-A06` 五个 Capability 读取 Router。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A05
输入基线：冻结API-01/API-04、DM-05、Schema0095、DEC-837～843
前置任务：GLOBAL Review受信持久化内核、Capability Subject及终态正式化已通过
涉及模块：capability api/application；review application/infrastructure；platform create_app
涉及实体：CapabilityBaselineVersion、Review、ReviewRound、ReviewEvent、AuditEvent、IdempotencyReceipt
涉及API：仅CAP_VERSION_SUBMIT_REVIEW；不含读取Router/生产组合
涉及权限：可信Origin、Session/CSRF、DeploymentAdmin、License、当前Reviewer及Subject资格
验收标准：首次原子送审、持久重放、撤权失败关闭、严格HTTP、默认404、真实PG与wheel
风险：due_at/submission_note无持久化基线、重放返回当前态冒充首次响应、Review/Subject半提交
```

## 实施结果

- 新增 Session/CSRF、DeploymentAdmin、License 和持久幂等外层；同一 UOW 内调用已验证 GLOBAL Review 内核和 Capability Subject，不复制评审状态机。
- 幂等收据指向首轮 Round，Review 仓储可从不可变首轮事实恢复首次响应，即使 Review 后续已终态也不伪造新送审。重放前仍重验当前管理员和 Subject 可访问性。
- Reviewer 规范排序后进入请求指纹和 Review 快照，防止同一集合仅因输入顺序形成不稳定结果。
- 新增 opt-in 送审 Router，默认应用保持404。CR-CAP-003明确首版对 `due_at/submission_note` 非空失败关闭，不静默丢数据。

## 验证与证据

- 定向单元/合同6项通过；覆盖原子提交、收据与Review同事务、持久重放/冲突/撤权、默认404、Origin/Session/CSRF/License、严格字段与安全错误。
- Win11/PostgreSQL 18.6 真实验证通过当前管理员、不合格Subject全回滚、Review/Subject/收据原子提交和持久重放；终态正式化回归同时通过。
- 后端全量2589项通过、3项按既定环境条件跳过；`compileall` 与 `git diff --check` 通过。
- 最终开发wheel内Capability/Review定向58项、解包Migration 4项通过；wheel SHA-256 `9289eea0d7a4b1a046d564dd186e2a19372d4c06ece5b99f3f3805602dba1d2d`。

## 兼容、回滚与未关闭项

无 Schema/Migration/依赖/配置/网络/Secret/外发变化。公开 URL/Operation 保持冻结 V1；非空调度信息按 CR-CAP-003 显式拒绝。停止注入 Router 即可回滚新 HTTP 流量，已形成的合法评审历史保留。

五个读取 Router、Windows 真实 HTTP 组合、前端、Review 通用时限/备注、正式信任/性能/Gate3/发行仍未关闭；本项不宣称生产可用。
