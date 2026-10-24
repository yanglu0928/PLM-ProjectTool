# SOL-06-A13-P08：结构化专项验证客户端与详情入口

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATE_FRONTEND_PASS`；完成安全前端传输、报告校验与用户可见维护提示，不表示真实 Edge 操作或送审已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P08`|
|输入基线|A13-P06 完整 HTTP 报告、A13-P07 Windows 真实组合；现有 SessionClient 与专项固定详情页；SectionVersion 验证的原操作号恢复模式|
|前置任务|后端请求/响应和首次观察语义稳定，详情页已有固定版本身份与写角色判断，可安全增加验证入口|
|涉及模块/实体|Vue 详情页、SessionClient、StructuredSpecValidateClient；无后端/数据库变化|
|涉及 API / 权限|调用既有冻结 VALIDATE；仅 ProjectManager、ImplementationMember 显示可用入口，项目成员仍可只读详情|
|验收标准|零正文 Session/CSRF/Key；严格校验完整报告、类型顺序、issue 与 valid/ready 派生；未知结果保留原 Key；页面逐项说明待维护信息且不暗示批准|
|风险|恶意/残缺响应被页面接受；断线换 Key 造成重复观察；报告与当前详情不一致；`valid=true` 被表述为可送审或批准；用户不知道如何处理 UNAVAILABLE|

## 实施与验证

- `SessionClient` 新增零正文、同源、CSRF 与 Idempotency-Key 保护的专项验证传输；传输结果未知时抛出不确定错误，由上层保留原 Key。
- 新增 `StructuredSpecValidateClient`，严格验证 20 个报告字段、八维事实、四类型精确有序检查、版本/摘要/计数、issue 顺序及 `valid/ready_for_review` 派生；跨项目、重排、未知状态、矛盾结论或异常响应全部失败关闭。仅项目负责人和实施成员可发起。
- 固定详情页增加“当前事实验证”：发送前将主体/项目/版本/Key 写入 sessionStorage；未知结果须明确勾选后按原 Key 重试，冲突或记录损坏锁定提交。报告必须与当前详情的系列、类型、版本、状态、两个摘要和四类计数完全一致，成功后才清理待决记录。
- 页面按中文展示八维事实和类型检查；每个非 PASS 项给出维护方向，明确验证只形成审计观察、不批准专项、不创建评审、不代表客户确认。即使 `valid=true`，只要 Trace 或业务类型证明缺失仍显示“尚不具备送审条件”。
- 定向客户端/详情页 2 文件、9 项通过；前端全量 146 文件、1810 项通过；完整 TypeScript/Vue typecheck 与 production build 通过。构建保留既有主 chunk 大小警告，无新构建失败。
- 首轮定向命令在 frontend 工作目录仍带仓库前缀导致工具路径未找到，同时新测试的数组展开不满足严格 tuple 类型；改正命令和测试调用后完整重跑，未修改产品边界或减少断言。
- 无外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项仅增加前端客户端、Session 传输和详情页区域；无 Migration、后端 API、角色、License、依赖或旧数据变化。重新构建静态前端即可升级；撤入口/客户端可回滚，服务端 Audit/收据历史不删除。

真实 Edge 与 PostgreSQL 页面点击尚未验证。Trace、非空 Artifact 及非结构类型 Owner 缺口继续由页面显示为待维护，不能送审；正式服务账户、公钥、HTTPS/Vault/ACL/CA、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P09` 完成 Windows 11 Edge→生产 Vue/Uvicorn→真实 Session/License/PostgreSQL 的专项详情验证验收，核对首次观察、原 Key 重放、页面提示、跨项目清屏及唯一收据/Audit。
