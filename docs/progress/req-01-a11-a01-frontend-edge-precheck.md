# REQ-01-A11-A01：Requirement 前端与 Edge 闭环前置核查

日期：2026-10-08。结论：`REQ_01_A11_A01_FRONTEND_PRECHECK_PASS`。下一项：
`REQ-01-A11-A02` Requirement 严格只读客户端。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A11-A01
输入基线：CR-REQ-001、冻结API-04、A10 Windows生产组合、用户的待办/原文定位UX要求
前置任务：REQ-01-A10-A02～A08全部PASS
涉及模块：frontend requirement client/view/router、Evidence Viewer、Project导航
涉及实体：只消费Requirement/Version/Source/Acceptance/Capability固定投影
涉及API：A10既有LIST/GET；后续写操作不在A02只读任务顺带开放
涉及权限：浏览器不推断权限；每次读取和Evidence定位由服务端重证Session/License/Project
验收标准：严格DTO、来源不复制正文、显式点击才定位、人工需维护项有逐字段提示、迟到响应丢弃
风险：把AI/模板当正式事实；页面展示UUID却不提供定位；复制来源正文；误把GET成功等同当前资格
```

## 对账结论

- 后端已提供Requirement identity和Version完整固定投影；来源只有固定对象ID、可选Version引用和
  Evidence引用，没有来源正文或Locator。前端不得根据UUID猜地址，也不得把列表摘要扩写成事实。
- 既有 `EvidenceViewerClient` 会重新核验PROJECT Evidence并返回受权固定文档版本及Locator；A11复用
  它实现“点击定位原文”，不新增重复的Requirement专用文档定位API。定位前页面只显示来源类型、
  固定引用和说明；点击后才请求Evidence Viewer，失败时保留明确错误而不显示旧结果。
- APPROVED_SURVEY_CONCLUSION和CONFIRMED_HANDOVER可提供业务记录入口；即便可导航，正式依据仍以
  Source自带Evidence引用的Viewer结果为准。HUMAN_DECISION没有独立读取API时显示“受控人工决定”及
  Evidence定位，不暴露内部表或伪造决定正文。
- “人工输入提示”落实为创建Version页面的结构化字段说明：来源类型/对象/固定Version/Evidence、
  可验收结果/方法/数据/环境/证据要求、能力匹配及人工确认、假设/排除/依赖。页面明确
  `PENDING_CONFIRMATION`不可送审，AI建议不能代替人工确认；不要求用户在表格中复制原文。

## 实施拆分

1. `A02`：实现Requirement identity/version严格只读客户端，拒绝多余字段、错父级、断裂ordinal、
   非规范时间/ETag/cursor和正文形状漂移。
2. `A03`：列表/详情路由与页面；显式点击Evidence定位，固定来源导航，人工维护提示和迟到响应隔离。
3. `A04`：结构化Version Draft客户端与页面；只覆盖冻结CREATE/VALIDATE/SUBMIT REVIEW，不新增旧
   analyze/match URL，也不把AI Candidate直接写成正式事实。
4. `A05`：Windows 11 Edge + PostgreSQL 18真实会话闭环，验证读取、定位、创建、校验、送审及
   断线/撤权/迟到响应；通过后进入A12 Workflow资格。

## 兼容、回滚与边界

- 无Schema/Migration、后端API、依赖、Secret、客户数据或外发变化；本项仅冻结前端实施边界。
- 页面和Router采用显式注册；回滚可移除前端入口，不影响A10后端或历史Requirement。
- A11不补通用能力目录前端、不实现AI原型执行、不绕开Evidence Viewer下载授权；缺少可核验
  Evidence时明确显示待补充，不把内部ID显示称为“已定位”。
