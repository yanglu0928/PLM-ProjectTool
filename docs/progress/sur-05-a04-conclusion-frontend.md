# SUR-05-A04：SurveyConclusion 严格前端客户端与工作台

日期：2026-10-07。结论：`SUR_05_A04_CONCLUSION_FRONTEND_PASS`。下一项：`SUR-05-A05`
Windows 11 真实 Edge / PostgreSQL 18 闭环。

## 实现结果

- 新增严格 `SurveyConclusionReadClient/WriteClient`，覆盖冻结 LIST、CREATE、GET、VALIDATE、
  SUBMIT_REVIEW 五项 Operation；响应执行 exact-field、Project/资源身份、排序、计数、时间、指纹、
  Location 与 Review ETag 校验。
- `SessionClient` 新增单次 Conclusion 写通道。VALIDATE 发送真正空请求体；CREATE/送审才带 JSON；
  所有写操作携带 CSRF 与原幂等 Key，网络结果不确定时由页面保留原 Key/正文，不隐式重试。
- 新增项目调研结论工作台：只允许从已关闭轮次、VALIDATED 答复、当前 ACTIVE Department/Member、
  ELIGIBLE Evidence 与未关闭 HND-03 待办中选择；部门/模块结论明确标为人工维护，模板与 AI 仅提示，
  不冒充客户确认事实。
- Evidence 不复制原文，用户点击后才读取 Evidence Viewer 描述并打开受权固定 DocumentVersion；
  open issue 使用稳定 `actionId` 深链，交接待办页读取后自动展开目标详情和维护提示。
- 创建、验证和送审采用写后重读；验证报告保留在当前页面并明确“验证不修改状态”。基础选择超过
  客户端单页安全上限时失败关闭，不以不完整候选生成结论。

## 边界、兼容与回滚

- 本项是计划内前端增量；未修改 Schema/Migration、冻结 `/api/v1` JSON、角色、依赖、Secret、
  License 或数据外发边界。未新增 Change Request。
- 可通过撤销 Conclusion 路由、客户端、工作台及待办 query 自动展开回滚；后端和既有业务历史不变。
- 当前不声称真实 Edge、Windows Server 2025、SUR-06、Gate 3、UAT 或发行通过；主 JS 仍有超过
  500 kB 的既知分块提示，留待独立前端性能任务处理。

## 验证证据

- 定向：Conclusion 客户端、工作台、Handover 深链共 15 项通过。
- 前端全量：88 个测试文件、1474 项全部通过。
- `vue-tsc` / Node TypeScript 类型检查通过。
- Vite production build：184 modules，JS 721.75 kB（gzip 178.54 kB），构建通过并保留分块提示。
