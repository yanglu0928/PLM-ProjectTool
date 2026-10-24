# CAP-02-A04：全局能力基线身份创建入口编码前检查

日期：2026-10-24；状态：`SOURCE_PASS / WINDOWS_EDGE_PG_PENDING`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `CAP-02-A04`：只解决管理员无法从合格固定 GLOBAL 来源创建 CapabilityBaseline 身份的问题；不在本项创建能力条目、送审或宣称已批准。|
|输入基线|Gate 2 冻结 Capability `POST /api/v1/global/capability-baselines`、五个 GET、Document GLOBAL 只读；`CAP-02-A03` 上传前端源码通过，实际 Edge/PG 待合成实测。|
|前置|后端 Baseline create 已于 CAP-01-A05-A07 接入 Windows 显式平台；服务端资格要求 1～500 个不重复 GLOBAL ACTIVE `STANDARD_CAPABILITY` 文档的 AVAILABLE 固定版本。前端 GLOBAL 文档/版本只读客户端存在。|
|模块/实体/API|CapabilityBaseline identity/create first receipt；`baseline_code/name/description/source_documents` 精确 DTO；成功 201 后独立读取基线当前事实，不在本项自动填充能力项/批准指针。|
|权限|仅 DeploymentAdmin 且可提交 Session 发起；SessionClient 保管 CSRF，服务端复核 Origin/Host、Admin、License、来源资格及幂等。|
|验收|文档/版本分页、同一文档只能选一个固定版本、无合格来源禁止提交；Strict 201/Location/ETag/no-store，网络不确定结果原 Key 恢复与会话变化清屏；普通成员/匿名拒绝；定向及全前端测试、typecheck/build，随后 Win11 Edge/PG 合成来源→身份创建实测。|
|风险|用户本地标准能力库未自动导入；无真实 GLOBAL AVAILABLE 来源时 UI 只能空态，不能制造假基线。身份创建结果 `current_approved_version_ref=null`，Handover 仍不可引用，直到版本及正式 Review 批准。|

此项不改后端 Schema/API/License 或冻结业务资格。前端只使用元数据，不读取/外发文档正文。

## 实施与源码验收

- 新增冻结 `CAP_BASELINE_CREATE` 的前端客户端与 SessionClient 私有 CSRF 桥接；严格验证管理员、1～500 个不重复固定来源、201 回执、Location/ETag/no-store、原操作号。
- 页面仅列出 GLOBAL ACTIVE `STANDARD_CAPABILITY` 文档，逐文档选择 AVAILABLE 固定版本；保留同号不确定结果记录，成功后跳转只读详情。创建回执的 `current_approved_version_ref` 必须为 null。
- 客户端 4 项、页面 4 项定向 PASS；前端全量 168 文件、1904 项 PASS，typecheck/build PASS。没有新增 Schema、后端 API 或第三方依赖。
- 尚未在 Windows 11 Edge/隔离 PG 用合成文档验证 A03 上传与本项创建的真实服务组合；没有正式已批准 CapabilityVersion，Handover 引用前置未满足，Pilot/Gate 仍 `NOT_READY`。
