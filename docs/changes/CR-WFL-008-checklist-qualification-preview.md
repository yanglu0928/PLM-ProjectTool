# CR-WFL-008：Checklist 权威资格预览读边界

- 日期：2026-10-06
- 状态：IMPLEMENTED / VERIFIED
- 触发 WBS：`WFL-01-A07-P07-A07`
- 关联：冻结 API-02 `WORKFLOW_GET` / `WORKFLOW_CHECKLIST_RECORD`、CR-WFL-004～007、DEC-894～899

## 偏差与原因

冻结 Checklist 写命令要求 `PASS` 请求中的 `evidence_refs` 与服务端
Handover 当前事实 Owner 结果精确一致。现有 `WORKFLOW_GET` 仅返回 Checklist
状态，Handover 分析/待办读投影也不包含固定来源及 Action 验证所需的完整
Evidence 集。因此前端无法既不猜测、也不要求用户手填 UUID 地构造合法
PASS 请求。

## 采用方案

新增兼容性读取端点：

```text
GET /api/v1/projects/{project_id}/workflow/checklist-items/{item_key}/qualification
Operation ID: WORKFLOW_CHECKLIST_QUALIFICATION_GET
```

- 仅支持已注册真实 Owner 的 `HANDOVER_BASELINE` 和 `HANDOVER_ISSUES`。
- 仅 ProjectManager 且 Project 为 ACTIVE 可读；权限精确复用
  `WORKFLOW_CHECKLIST_RECORD` 策略，不新建更宽的读权。
- 在一个调用方事务内重验 License、Session、Project 身份、当前 ACTIVE
  Handover Workflow，并调用 Handover Owner 重验当前 Review/Document/Evidence/
  Capability/AI/Action/Trace 事实。
- 成功只返回 Workflow/Project/Item 身份、当前 Item 状态、Workflow 强 ETag、
  当前 Handover Version 引用、ReviewRound 引用及规范 Evidence UUID 集。不返回
  文档正文/路径、AI 内容、锁版本、内部摘要或失败细节。
- 无资格统一返回 `WORKFLOW_GATE_NOT_SATISFIED` 409；非当前阶段返回
  `CONFLICT_STATE` 409；不向前端泄露具体哪个受保护事实失败。
- 预览是短时建议，不是授权能力或 Gate 事实。写命令仍必须携带返回的
  ETag 并由服务端重新完整复验。

## 兼容、迁移与回滚

- 这是 `/api/v1` 非破坏性新读端点；不修改冻结请求/响应 DTO 和错误语义。
- 无 Schema/Migration、新表/列、新依赖、Secret、网络或客户数据外发。
- 新 Router 继续显式注入；默认应用保持 404。回滚可停止注入并删除新
  Service/Router，既有 Workflow/Checklist 历史不受影响。
- 前端在本端点完成前保持 Checklist 写入按钮未接线，不退化为手填 UUID。

## 风险与验证计划

- 风险：资格复验包含物理文件字节校验，GET 延迟可能高于普通读取；保留
  `Cache-Control: no-store`，性能结论留 20 并发门客观测量。
- 风险：预览与写入之间的 Evidence/Review/Workflow 可变；强 ETag 加写时再复验
  使变化失败关闭。
- 测试：Application 正反例/权限/许可/身份/状态/漂移；HTTP 安全/投影/
  ETag/默认 404/错误投影；相关回归与后端全量。生产组合及真实 Win11/
  PostgreSQL 闭环可作为后续独立 WBS。

实施结果：新增 Application Service 和显式注入 Router，默认应用仍 404；定向 9 项、
相关 32 项、后端全量 2763 项运行/3 项条件跳过全部通过。开发 wheel 包含新模块，
SHA-256 `c97424723d7698d249179422cfc3c9592b1acc3c8741fc363e92658bdc7c3e49`。
