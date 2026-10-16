# REQ-01-A11-A03：Requirement 读取与原文定位页面

日期：2026-10-08。结论：`REQ_01_A11_A03_READ_LOCATE_VIEW_PASS`。下一项：
`REQ-01-A11-A04` Requirement Version Draft 结构化写入页面。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A11-A03
输入基线：A11-A01定位边界、A11-A02严格只读客户端、既有Evidence Viewer
前置任务：A11-A01～A02 PASS
涉及模块：frontend Requirement views/router、Project详情入口
涉及实体：Requirement、RequirementVersion固定快照及Evidence引用
涉及API：REQ_LIST/GET、REQ_VERSION_LIST/GET、PROJECT Evidence Viewer
涉及权限：客户端不推断授权；每次读取/定位均由服务端按当前Session重证
验收标准：身份门禁、分页/路由迟到结果隔离、字段维护提示、显式点击后定位、无正文复制
风险：摘要冒充正文；内部ID猜路径；未确认项误送审；跨版本迟到Evidence覆盖当前页面
```

## 结果

- 新增项目需求列表与详情路由；Project详情增加需求入口。列表只显示安全identity摘要，失败、刷新、
  换项目均清空旧数据，分页拒绝不保留不完整集合。
- 详情分层读取Requirement、Version摘要及用户选中的完整固定版本；明确展示验收五要素、能力匹配、
  假设/排除/依赖和AI Task，`PENDING_CONFIRMATION`明确禁止当作正式事实或提交正式评审。
- 固定来源只展示类型/标识和安全业务导航；HUMAN_DECISION不猜内部路径。Evidence仅在用户明确点击后
  调用既有PROJECT Viewer并重新鉴权；版本/路由变化会清除结果并丢弃迟到响应。短预览明确不是权威正文。
- 新增8个页面场景；完整前端91个测试文件、1516项、typecheck与生产build通过。构建保留既有
  `>500 kB`单chunk警告，A03不跨WBS做代码分割。
- 无Schema/Migration、后端API、依赖、Secret、客户数据或外发变化。回滚可撤两个页面、路由及入口，
  不改变后端或历史数据。真实Windows Edge/PG闭环留A05，不能以组件测试代替。
