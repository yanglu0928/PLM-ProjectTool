# REQ-01-A12-A06：Requirement Workflow前端

日期：2026-10-08。结论：`REQ_01_A12_A06_WORKFLOW_FRONTEND_PASS`。下一项：
`REQ-01-A12-A07` Windows 11 Edge真实浏览器闭环。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A06
输入基线：CR-REQ-004、A05真实PG/HTTP结果、既有Workflow页面安全交互
前置任务：REQ-01-A12-A05 PASS
涉及模块：Session写边界、Workflow资格/记录/推进客户端及ProjectWorkflowView
涉及实体：无Schema；只消费服务端最小投影和不可变首次回执
涉及API/权限：扩展既有/api/v1三个客户端的允许值；Session/CSRF/角色/License边界不变
验收标准：严格聚合响应、两个Requirement item写入、推进PROTOTYPE、UUID不显示、漂移失败关闭
风险：把聚合数组降为单值；页面暴露内部UUID；持久重试接受未知item/target；跨阶段写入
```

## 实现结果

- Qualification客户端新增严格Requirement响应variant，只接受非空、唯一且等长的Version/ReviewRound数组
  以及非空Evidence；旧Handover/Survey仍要求单`review_round_ref`，跨variant字段或额外字段拒绝。
- Session及Checklist客户端将两个Requirement item加入显式allowlist；当前Workflow Stage不匹配时请求不发送。
- Transition客户端新增唯一映射`REQUIREMENT -> PROTOTYPE`，响应必须精确匹配推导结果；本地未确定操作
  校验同步纳入PROTOTYPE目标，不接受任意阶段。
- 页面只展示正式需求版本、真实批准轮次和固定依据的数量，不显示内部UUID；提交时仍由服务端重验，
  首次回执继续明确不代表当前状态或Gate通过。

## 验证、兼容与回滚

- 前端全量93个测试文件、1532项全部通过；Vue/TypeScript类型检查和Vite生产构建通过。
- 构建仅保留既有大chunk警告（JS约776.54 kB，gzip约191.66 kB），未引入新依赖。
- 无后端代码、Schema/Migration、公开路径、权限、Secret、客户数据或外发变化；撤新增variant/allowlist/
  映射及页面计数即可回滚，既有Handover/Survey行为不变。
- 本项是自动化前端合同验证，不替代真实Edge；A07执行浏览器闭环。Gate 3、UAT、三平台和发行未通过。
