# SUR-05-A01：SurveyConclusion HTTP / Windows / UI 前置核查

日期：2026-10-07。结论：`SUR_05_A01_CONCLUSION_HTTP_UI_PRECHECK_PASS`。下一项：
`SUR-05-A02` 五个冻结 Conclusion Operation 的严格 HTTP 边界与 cursor。

## 现状与边界

- 冻结 API-04 只有五个 Operation：LIST、CREATE、GET、VALIDATE、SUBMIT_REVIEW；公开路径固定为
  `/api/v1/projects/{project_id}/survey-conclusions` 资源族，不新增修改、删除、latest 或专用审批路径。
- A04～A06 已提供五项内部 Owner；当前没有 Conclusion Router、Windows 生产装配、前端客户端或页面，
  因而外部仍不可用。通用 PROJECT Review Router继续负责决定/退回/撤回，本阶段只提供业务送审捷径。
- LIST 使用会话/项目/页长绑定的HMAC keyset cursor，位置为`created_at + survey_conclusion_id`；从既有
  Survey cursor key以固定标签派生，不新增部署Secret。列表只返版本摘要，GET 才展开部门/模块结论及
  固定 Evidence/open issue refs，不复制外部正文、路径或私表身份。
- CREATE 请求严格包含 survey、round、部门/模块结论、Evidence角色、open issue、AI task和可空
  supersedes；未知字段拒绝，正式排除/风险接受字段继续不开放。VALIDATE 请求体必须为空并使用持久
  幂等Key。SUBMIT_REVIEW沿用ReviewSubmissionRequest四字段，其中V1要求`due_at/submission_note=null`。
- ValidationReport公开valid、blocking issues、warnings、coverage summary、checked_at及固定Conclusion身份；
  报告不改变状态。所有返回都使用`no-store`，业务错误只映射冻结错误目录，不暴露数据库或内部异常。

## 用户交互

- Conclusion页面以实际调研事实为主，模板/AI仅提示且不冒充客户确认；创建表单明确提示必填来源与人工
  维护内容，不要求客户填写模板表格。
- Evidence项提供受权Evidence Viewer入口；HND-03 open issue提供待办详情定位。定位只传公开稳定资源ID，
  不把文档正文复制进表格，也不猜测内部row identity。
- 页面采用写后重读；未知结果保留原幂等Key与请求上下文，不自动轮换或在客户端推断成功。

## 实施拆分与验证

1. `SUR-05-A02`：严格HTTP DTO、Conclusion cursor、合同测试。
2. `SUR-05-A03`：Windows显式组合、真实FastAPI/PostgreSQL 18闭环及Review registry双Subject回归。
3. `SUR-05-A04`：严格前端客户端、Conclusion工作台和Evidence/open issue点击定位。
4. `SUR-05-A05`：Windows 11真实Edge端到端闭环；失败则记录CR并向前修复。

本项为静态核查，无代码、Schema/Migration、冻结API、依赖、Secret、网络、客户数据或外发变化；不代表
HTTP/UI、Windows Server 2025、SUR-06资格、Gate 3、UAT或发行通过。
