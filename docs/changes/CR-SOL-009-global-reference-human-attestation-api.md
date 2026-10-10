# CR-SOL-009：GLOBAL Reference 人工脱敏确认的受权 API/交互入口

日期：2026-10-09；状态：按 CR-EXEC-001 持续授权先登记，待分项实施验证；原 Gate 2 冻结 API-04 提交 `64cdf09` 保留不追写。

## 冲突与证据

冻结 API-04 已定义 GLOBAL `SOL_REFERENCE_CREATE`，仅 DeploymentAdmin 可写；CR-SOL-006/007 已要求固定来源集合指纹与实际管理员人工脱敏确认。当前内部 `ReferenceDeidentificationConfirmService`、当前 Proof、撤回 Owner 与 0140～0143 账本已经存在，并通过隔离 PG/私有文件合成验证；但冻结 API-04 的公开 Operation 表没有 Preview/Confirm/Revoke 路径，Windows 生产组合未挂载确认入口，用户无法逐条检查后形成真实确认。脚本中的合成声明不能冒充真人确认。直接开放 GLOBAL Create 会绕过实际交互前置或令管理员只能离线调用内部方法。

## 方案比较与决定

- 不选将 AI 输出、`deidentification_class`、Audit 或合成夹具自动视为人工确认；均缺实际操作者、固定来源、可撤回有效期和可见原文。
- 不选修改冻结 `SOL_REFERENCE_CREATE` 的路径/请求或取消 GLOBAL 确认；会破坏冻结合同或安全不变量。
- 选择在 `/api/v1/global` 兼容新增三项独立白名单操作：`SOL_REFERENCE_DEIDENTIFICATION_PREVIEW`（受权只读预览，不写账本）、`SOL_REFERENCE_DEIDENTIFICATION_CONFIRM`（明确人工勾选/短有效期、当前 Session+CSRF+License+DeploymentAdmin+幂等与写时来源重验）、`SOL_REFERENCE_DEIDENTIFICATION_REVOKE`（当前管理员、原因码、幂等与 Audit）。UI 先展示固定 Document/Evidence 身份和既有原文定位入口，提示来源/内容可能变化；只有人主动确认才能 POST。服务端自行计算来源指纹，客户端不能指定确认人、来源 Hash 或 Audit。新操作不由业务 AI/Job 调用，默认应用不装配，Windows 仅在所有真实依赖可用时显式启用；GLOBAL Reference 创建另在此链通过后接线。

P08-P02 增量合同补充：Preview 的服务端指纹仅供 Confirm 作预览过期栅栏；Confirm 必须带回预期指纹，服务端仍从当前物理来源重新计算并比对，绝不把客户端指纹当成来源证明。新增操作和错误边界见 `docs/api-contract/solution-reference-deidentification-v1-increment.md`。

## 差异、风险、迁移/回滚与验证

相对冻结 API-04 是新增操作，不改已有 `/api/v1` 方法、字段、错误、权限或既有 PROJECT Reference；按正式 API Change Request 追溯。无新实体/Schema/依赖或历史数据自动迁移。风险为前端把预览视为当前确认、来源预览与提交之间漂移、失密/撤权重放、错误地在 UI 自动勾选；确认 Owner 必须写时独立复验，预览不生成确认，UI 每次要求显式人工动作，确认回执也不代表 GLOBAL Reference 已创建。撤回账本只追加受控状态，不删除历史。

回滚先停用新增三路由和 UI，保留已生成的确认/Audit/收据；不得直接删除已有人工确认。验证按单项完成：请求白名单/错误/权限/CSRF/幂等合同；真实 Auth/Document/Evidence/PG/文件的过期、撤权、物理漂移、重放、Audit 回滚；Windows 缺信任源关闭；真实 Edge 人工点击路径（仍使用合成资料，仅验证交互机制，不能声称客户正式确认）。未完成前 GLOBAL Create、Gate 3 与发行仍关闭。

TraceLink：冻结 API-04/DM-05 → CR-SOL-006/007 → 0140～0143/内部确认与 Proof → 本 CR → SOL-01-A04-P08-P02～P06 → GLOBAL 创建与正式发行验收。
