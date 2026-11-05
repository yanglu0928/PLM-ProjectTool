# OUT-01-A01-P30 验收结果：Output 不可重试失败原子终态

- 日期：2026-11-05
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-026
- Hosted run：[41959590610](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41959590610)

## 实现与验证

- 新增内部 Output Generation Failure Owner 与 SQLAlchemy repository。它锁定并校验 OutputRequest，再核验精确的当前 Output lease；调用 Jobs retry_or_fail(retryable=false)，同一 UnitOfWork 内更新 Output 为 FAILED、completed_at、lock_version 并记录 SYSTEM Audit。
- 输入仅接受三个固定不可重试错误代码，不保存自由文本或堆栈；插件、渲染、文件系统、API、默认组合均未接入。
- hosted PG18.6 verifier通过：有效claim使Job/Output原子失败且释放lease；错worker、旧fencing token、非白名单错误拒绝；Audit注入失败使Job/Output/lease全回滚；Audit actor为受控system actor，original_actor为请求者。
- 后端4042 tests/wheel、前端测试/build、PG18/pgvector重建、同run父包组装及PostgreSQL生命周期smoke、A17/A34/A35/A50通过。P25为独立失败项，initdb仍返回0xC0000135，真实HTTP/Edge未执行；整体workflow不全绿。

## 范围与限制

- 无Schema/Migration/API变更，无客户数据、外部API、插件执行或输出文件。
- 仅GitHub hosted Windows Server 2025 D盘runner；用户本机/C盘代码及测试执行为零。
- P30不代表实际Worker/服务账户、重试策略、Plugin信任、DOCX生成、Win11实机、Gate/Pilot/正式Release通过。
