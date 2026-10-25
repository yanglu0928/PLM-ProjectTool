# REQ-01-A10-A05：RequirementVersion 四个冻结 HTTP

日期：2026-10-08。结论：`REQ_01_A10_A05_VERSION_HTTP_PASS`。下一项：
`REQ-01-A10-A06` RequirementVersion 原子送审。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A05
输入基线：冻结API-01/API-04、REQ-01、CR-REQ-001、Migration0115
前置任务：A02 identity读取Owner、A04 Requirement HTTP均PASS
涉及模块：RequirementVersion API/cursor、Version读写/校验Owner、通用App Router注入点
涉及实体：RequirementVersion、RequirementVersionValidation、AuditEvent、IdempotencyReceipt
涉及API：REQ_VERSION_LIST/CREATE/GET/VALIDATE
涉及权限：Project member读取；PM/Implementation创建；PM/Implementation/CustomerManager校验
验收标准：专用签cursor、严格DTO、完整固定快照、安全错误、ETag/If-Match、幂等、默认关闭
风险：跨父资源cursor重放；固定快照字段丢失；校验回放trace混同；错误投影泄漏
```

## 结果

- 新增独立 `RequirementVersionCursorCodec`，以独立32字节key和`requirement-versions`
  family绑定Project、Requirement、Session摘要、page size及`version_no`位置；拒绝跨父资源重放。
- 新增opt-in Router，按冻结路径实现LIST/CREATE/GET/VALIDATE；完整投影固定版本的来源、验收
  标准、能力评估、假设、排除、依赖、AI任务引用、分类、状态、审计时间和根ETag。
- CREATE执行强If-Match与持久幂等；VALIDATE执行持久幂等且不要求If-Match。幂等校验回放保留
  首次不可变审计证明的trace，HTTP envelope仍返回本次请求trace，避免把合法重放误报503。
- 严格限制2 MiB JSON，拒绝重复key、NaN/Infinity及未知字段；输出按资源、父级、状态和类型
  失败关闭；通用应用仅在显式注入时开放，Windows正式组合留A08。
- 定向cursor/HTTP 7项通过；完整后端3054项通过、3项跳过。
- Windows 11/PostgreSQL 18.6真实四Operation、cursor、完整快照、根ETag、create/validate回放、
  当前事实校验、角色/License拒绝、Audit、receipt及Alembic drift通过。
- 开发wheel共1160项，SHA-256
  `8233086387658ada40cdcc9e7fde52e805f768efe4b488b831be8b401db82b18`。
- 首次误用仅含运行依赖且未安装pytest的PoC解释器，测试未执行；随后使用仓库正式unittest
  入口执行。首次完整回归还暴露三个Requirement cursor负例把末字符固定改为`A`，原字符恰为
  `A`时token未变化而随机失败；已改为确保字符不同，并以完整重跑结果收口。无Schema/Migration、
  依赖、Secret、客户数据或外发变化。
