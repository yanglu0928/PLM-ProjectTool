# REQ-01-A11-A04：Requirement Version Draft 结构化写入页面

日期：2026-10-08。结论：`REQ_01_A11_A04_DRAFT_WRITE_VIEW_PASS`。下一项：
`REQ-01-A11-A05` Windows 11 Edge + PostgreSQL 18真实闭环。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A11-A04
输入基线：冻结REQ_VERSION_CREATE/VALIDATE/SUBMIT_REVIEW、A11-A01～A03
前置任务：A10 Windows写组合及A11-A01～A03 PASS
涉及模块：frontend Session transport、Requirement write client/draft view/router
涉及实体：RequirementVersion不可变快照、Validation Report、Review/Round引用
涉及API：POST Version create/validate/submit-review；不新增URL或响应字段
涉及权限：写入依赖重新登录取得的私有CSRF；浏览器摘要不替代服务端角色/License重证
验收标准：结构化逐字段提示、强根ETag、原幂等Key、严格响应、PENDING禁止送审、评审人可读选择
风险：AI建议冒充事实；未知结果重复提交；技术ID误填；校验通过误称评审通过
```

## 结果

- SessionClient新增三个冻结Requirement Version写操作的专用受控传输：create携带根强ETag和JSON，
  validate为空body，submit-review只发送冻结策略；三者均保留调用方Key且不自动重试未知结果。
- 新增严格写客户端，完整预检Source、验收五要素、Capability人工评估、边界列表和AI引用；严格核验
  201 Location/ETag、Validation coverage及Review `REQ-03 + REQUIREMENT_ALL_V1`父级和评审人顺序。
- 新增结构化草稿页面：逐字段说明需要维护什么，不复制来源正文；以当前Requirement ETag创建不可变
  Draft，创建后必须运行服务端校验。`PENDING_CONFIRMATION`即使校验valid也禁止送审；非待确认项只能
  从服务器返回的有效项目成员中选择评审人，送审回执明确不是批准结论。
- 首版能力目录尚无冻结前端只读端点，因此Capability为可选人工区，要求从受控基线记录取得固定UUID，
  不猜内部URL或自动确认；此限制保留至后续能力目录UX，不以AI填充绕过。
- 新增8个客户端/页面场景；完整前端93个测试文件、1524项、typecheck与生产build通过。构建保留既有
  `>500 kB`单chunk警告。真实Edge/PG、撤权/断线和未知结果实链留A05。
- 无Schema/Migration、后端API、依赖、Secret、客户数据或外发变化；回滚撤专用transport/client/page/
  route/detail入口即可，后端与历史版本不变。
