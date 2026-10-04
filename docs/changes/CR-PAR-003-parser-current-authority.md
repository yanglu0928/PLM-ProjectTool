# CR-PAR-003：Parser 独立 Worker 的现时授权复核

日期：2026-09-30；状态：按 V1.1 持续授权实施中；Gate2 原冻结 `64cdf09` 保留，Gate3 不变。

## 来源与冲突

ADR-007 要求独立 Worker 继承原用户、Project 和目的，不把 SystemActor 当作业务通配。当前 Parser 内部步骤验证已提交上传和 Job/Outbox，却尚未在长任务准备及最终发布时复核原用户启用状态、Project 当前角色/归档状态与 License。直接装配进程会在上传者撤权或 License 失效后仍可能发布新解析事实，不满足既有安全基线。

## 方案比较与选择

- A：只信上传时授权及 Job 来源，最少改动但长期异步任务可能越权；不选。
- B：用 Auth 当前启用 User Port、Project Application 授权 Port 与 License Guard，在 Parser 准备和最终发布的短事务内按原 actor/scope/trace 重新核验；项目角色与现有上传允许角色相同，GLOBAL 仅部署管理员。选择 B，不保存 Session/Cookie，SystemActor 只表明执行来源。清理性的取消/失败/过期恢复不因原用户后来撤权而禁止，以免永久卡在 RUNNING。

## 差异、影响、迁移/回滚

新增内部 `DOCUMENT_PARSE_PROCESS` Project 操作，角色仅 `PROJECT_MANAGER`、`IMPLEMENTATION_MEMBER`、`CUSTOMER_MANAGER`，PROJECT 归档拒绝新结果；与现有上传角色对齐，不扩大公开 API 权限。无 Schema、`/api/v1`、技术栈、依赖或生产数据迁移。Worker 在授权撤销时可在当前安全点失败关闭；原 Lease/重试次数继续受 Jobs 管理，不把拒绝写成成功。回退须停独立 Parser Worker，并保留已有 Job/Audit/ParseRecord 历史；不能通过回退恢复越权发布。

## 验证与未决

单元验证启用/停用 User、Project 角色与归档、GLOBAL 管理员、License 拒绝、错误来源及零写；真实 PG/HTTP 夹具验证长任务准备/发布前撤权、正常链和故障回滚；全量/wheel。后续正式进程组合须注入当前账户 SystemActor/License/Project，并验 Windows11；Server2025/Debian、生产信任锚、Gate3/发行另验。未通过前本 CR 与 P05 整体保持 INCOMPLETE。

2026-09-30/P05-A02-P01：上述内部授权 Port/角色策略和准备/发布调用者事务已实现。Windows11 隔离 PG18/真实合成上传的 User 停用、成员暂停、License 失效拒绝和恢复后唯一结果 PASS；后端1646（3既有跳过）、wheel PASS。正式进程组合和目标账户信任源仍缺，CR 不据此关闭 Gate3/发行条件。
