# SOL-06-A13-P09：结构化专项验证 Windows 11 浏览器闭环

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATE_WINDOWS_BROWSER_PASS`；仅为 Windows 11 合成信任与可弃数据验收，不表示专项已批准、Gate 3 或正式发行已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P09`|
|输入基线|冻结 `SOL_SPEC_VALIDATE`；A13-P06 HTTP 合同、P07 Windows 组合、P08 前端详情入口；既有 SOL-06 Edge/PG 一次性夹具|
|前置任务|生产组合已具备真实 Session、CSRF、License、来源 Owner、PostgreSQL 收据/Audit；前端 production build 已通过|
|涉及模块/实体|仅扩展验收夹具；StructuredSolutionSpec 固定详情和 ValidationReport；无产品代码或 Schema 变化|
|涉及 API / 权限|调用既有 `POST .../{spec_id}:validate`；ImplementationMember 发起，跨项目保持 404|
|验收标准|首次现时观察、原 Key 重放、中文维护提示、跨项目清屏、唯一收据和 Audit|
|风险|浏览器缓存或历史报告泄漏；断线换 Key 形成重复观察；合成信任被误写成正式发行证据|

## 实施与验证

- 在共享浏览器服务器中增加显式 `spec_validation_mode`，只在该模式装配正式 Windows VALIDATE Router；默认详情、列表、修订模式均保持原组合，不增加测试专用产品入口。
- Windows 11 本机 Edge 通过已构建 Vue 登录合成 ImplementationMember，创建专项并打开固定详情，真实点击“验证当前事实”；生产 FastAPI/Uvicorn 经 Session、CSRF、License、项目授权和当前来源 Owner 访问 PostgreSQL 18.6，返回完整报告。
- 页面证明固定内容、载荷、Requirement、Section、Evidence、空 Artifact 和系列当前版本通过；Trace 为 `UNAVAILABLE`，显示具体维护方向和“尚不具备送审条件；不得视为已批准”，迁移专项 `SCOPE_MAPPING` 类型检查通过。
- 保存首次请求的原 Idempotency-Key 后离开详情再返回，页面恢复结果未知状态、隐藏旧报告并要求人工勾选；真实重试沿用原 Key、仍返回 200，成功后清除待决记录。数据库最终只有一条 `V1_SOL_STRUCTURED_SPEC_VALIDATE` 收据和一条 `SOL_STRUCTURED_SPEC_VALIDATED` Audit。
- 跨项目直接 VALIDATE 返回 404；切换到无权项目详情后不再显示原正文或验证报告，未出现跨项目 200。
- P09 完整 Edge/PG 链通过；共享夹具的 A10-P05 旧详情 Edge/PG 回归通过；Node 语法、Python 编译和 Alembic 无新增升级操作检查通过。首轮在注入合成待恢复记录时浏览器表达式语法错误，临时资源自动清理；改为先序列化记录字符串后完整重跑通过，未修改产品行为或减少断言。

## 兼容、升级、回滚与遗留

本项仅增加显式验收模式和独立启动脚本；无 Migration、冻结 API、角色、License 权益、依赖、产品静态资源或旧数据变化，无用户升级动作。撤除该验收模式即可回滚，产品 Audit/收据历史不受影响。

TraceLink Owner、非空 OutputArtifact 与非结构专项业务证明仍未完成，因此当前合成专项不能送审。正式服务账户、公钥、License/Vault/ACL/CA、HTTPS、Windows Server 2025、Debian 13、20 并发、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A14-P01` 核对冻结 `SOL_SPEC_SUBMIT_REVIEW`、统一 Review Engine、专项状态/版本锁定、VALIDATE 报告与 Trace/Artifact 前置，定义失败关闭的送审边界和后续分项实现顺序。
