# HND-01-A06-A01：Handover 前端与交互前置核查

日期：2026-10-05。结论：`HND_01_A06_A01_FRONTEND_PRECHECK_PASS`。下一项：`HND-01-A06-A02` Analysis 五读严格前端客户端。

## 核查结论

1. Handover Analysis 的 11 个冻结 Operation 已具备 Windows 显式生产组合，但前端没有 Handover 模块、路由、客户端或页面；不能以 AI 建议页、Excel 评审表或聊天输出代替正式 Handover 业务视图。
2. `AnalysisItem` 已提供 `evidence_refs`、`confirmation_question`、`required_input_spec`、选项、建议、影响和优先级。前端应把这些内容显示为问题卡片和结构化“需要维护什么”提示，不把 AI 建议或空白输入框当已确认业务事实。
3. 现有 Evidence Viewer 已能按 EvidenceId 重新验证当前权限、固定 DocumentVersion、来源指纹与 locator，并返回受控原文位置/下载入口。因此 Handover 页面应提供逐 Evidence 的“定位原文”动作，按点击获取位置；不得把原文、存储路径或大段摘录复制进列表或表格。
4. 当前 Handover Action 公共边界只有 LIST/GET；CREATE/PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL 的内部 Owner 已有，但尚无写 HTTP。前端不得绕过 Owner 直写或伪造按钮成功。Analysis 读取页面可先独立交付，Action 写 HTTP/页面按独立 WBS 补齐。

## 交互与安全边界

- Analysis 列表只显示目的、状态、正式版本引用和更新时间；详情/版本/Item 按用户动作分层加载，cursor 不持久化到 URL、localStorage 或日志。
- Item 卡片明确区分 `GAP/MISSING/CONFLICT/RISK/SCOPE/NEED_CONFIRM`、候选/已确认等服务器状态；`NEED_CONFIRM` 必须显示确认问题、影响、服务器选项和字段级维护说明。
- “定位原文”按 EvidenceId 调用 Evidence Viewer；定位失败清空旧位置并显示安全错误。离开 Item、切换项目、撤权或会话变化时清空位置，不缓存正文。
- AI Task、Capability、Document、Evidence、Review 和 Action 只以受控引用或既有 Owner 页面导航连接；Handover 客户端不越层拼接内部数据或从 UUID 推断权限。
- 写操作继续使用 Session 私有 CSRF、强 ETag、原幂等 Key 和未知结果保护；本前置任务不开放写 UI。

## 后续拆分

- `A02`：Analysis 五读严格前端客户端，完整验证 Envelope、DTO、父级绑定、ETag、cursor 和安全错误。
- `A03`：Analysis 列表/详情/版本/Item 页面与项目导航；问题卡片接 Evidence Viewer 定位和结构化人工维护提示。
- `A04`：Action LIST/GET 严格客户端与只读待办页，保持 SUBMITTED≠CLOSED。
- 后续独立任务：Action 七个写 Operation 的 HTTP/Windows 组合与前端状态动作；Analysis 创建/升版/校验/送审交互；真实浏览器/PostgreSQL 闭环和 Workflow Checklist Adapter。

## 影响与验证

本项为静态前置核查，不改变程序、Schema、Migration、冻结 API、依赖、配置、Secret、网络或客户数据。已交叉核对冻结 API-04、Handover Windows 组合、Analysis/Action DTO、现有 AI 建议页、Document 页面和 Evidence Viewer。结论不代表前端、浏览器、Action 写入、正式 key/信任、Gate 3、UAT 或发行通过。
