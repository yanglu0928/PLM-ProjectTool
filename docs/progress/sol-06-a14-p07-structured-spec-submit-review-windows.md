# SOL-06-A14-P07：结构化专项送审 Windows 显式写组合

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_SUBMIT_WINDOWS_PASS`；已完成 Windows 11 显式写模式的真实 HTTP/PostgreSQL 18.6 送审闭环，不表示前端、浏览器、正式信任、Windows Server 2025、Debian 13 或 Gate 3 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P07`|
|输入基线|API-04 冻结 `SOL_SPEC_SUBMIT_REVIEW`、CR-SOL-021、DEC-1210、A14-P04～P06 状态/Owner/原子服务/HTTP Router|
|前置任务|当前事实重证、精确 Trace、统一 Review 状态、持久收据重放和默认关闭 HTTP 合同均已通过|
|涉及模块/实体|Windows Solution 组合、生产启动装配、统一 Review/Project/Auth/License/Document/Evidence/Trace 依赖；无新实体|
|涉及 API / Schema / 权限|冻结路径、请求、响应、角色、License 权益、Schema 和依赖均不变；仅在 `include_secret_write` 显式写模式创建并挂载 Router|
|验收标准|缺任一受信依赖启动失败；默认/只读不暴露；跨项目、成员角色、License 失败关闭；当前事实失败后同 Key 可成功；成功可精确重放；漂移冲突；Review/Round/状态回执/平台收据/Audit 唯一|
|风险|误挂只读模式；以历史验证代替当前事实；失败占用幂等键；重复落账；客户端伪造系列或绕过 ProjectManager|

## 实施结果

- 新增 `create_windows_structured_spec_review_submission_router`，以 Windows 正式组合方式装配真实 Session、Origin、License、Project 授权、Reviewer 资格、Document/Evidence 固定来源、Requirement/SOL-06 Trace Owner、当前事实评估、统一 Review 持久化、状态 Owner、Audit 和幂等收据；任一必要依赖缺失即启动失败。
- `production_login` 只在 `include_secret_write` 下创建并向应用工厂注入送审 Router；默认、登录和只读路径不构造该写链，沿用 P06 的默认 404 边界。
- 请求路径版本仍由服务端解析不可变系列，送审时在同一事务重建当前来源与就绪事实；没有把前端输入或历史 VALIDATE Audit 当作授权事实。
- 为复用完整真实数据链，P03～P05 验收回调透传新增的 Session/CSRF/来源夹具参数；产品代码和既有验收语义不变。

## 验证证据

- Windows 11 / PostgreSQL 18.6 / FastAPI TestClient 真实组合通过：缺依赖拒绝、默认 404、跨项目 404、ImplementationMember 404、License 403、当前 Evidence 不合格 422、恢复后同一 Key 201、精确重放 201、新 Trace、请求漂移 409。
- 数据库核对仅存在一组 Review、首轮、`START` 状态回执和平台幂等收据；首次成功 Trace 下恰有 `REVIEW_CREATED`/`REVIEW_STARTED` 两条 Audit；同系列旧 APPROVED 指针保留。
- 组合/合同/服务定向回归：`15 passed, 73 subtests passed`；后端全量：`3748 passed, 3 skipped, 5854 subtests passed`。
- Python 开发 wheel 共 1415 项，包含 Windows 组合、生产入口和送审 Router，SHA-256 `b533d75c1afa9b0beb50b4b536ffea3b6bcf8ad883b64de44d53eb06f830f84e`。该 wheel 不是 Pilot 或正式发行包。

## 偏差、兼容、升级与回滚

- 首轮验收夹具通过正常写入把 Evidence `lock_version` 前推，恢复 eligibility 后仍因固定版本已漂移而被产品正确拒绝；未放宽产品规则，改用全新可弃数据库。
- 第二轮尝试只恢复 eligibility 被 Evidence Guard 正确拒绝为无版本变更写入。最终仅在可弃验收数据库中临时关闭触发器复制执行，完成原状态的精确切换/恢复；产品请求仍完整通过正常 Owner、Guard、事务和 Audit 链。该夹具手段不进入产品运行代码。
- 随后一次隔离 PostgreSQL 启动失败且未留下服务或监听；新建隔离实例重跑后完整通过，记录为环境瞬态，不据此降低验收。
- 无 Migration、冻结 API/权限、License、依赖或旧数据变化；后端同版本升级即可。若需回滚，可关闭 `include_secret_write` 下的 Router 注入，但已经产生的 Review、状态、Audit 与收据必须保留。
- 正式服务账户/公钥信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P08` 实现前端安全送审客户端和固定版本详情动作；只对当前用户可发起且服务端报告 `ready_for_review=true` 的最新 DRAFT 提供操作，明确 Reviewer 选择、幂等、冲突/就绪/License 提示，并保持服务端为最终裁决者。
