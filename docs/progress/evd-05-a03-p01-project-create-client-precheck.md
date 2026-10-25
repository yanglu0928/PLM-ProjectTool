# EVD-05-A03-P01：项目 Evidence 候选创建客户端编码前检查

日期：2026-10-25；状态：`FRONTEND_CLIENT_PASS / UI_AND_PACKAGED_PROOF_PENDING`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `EVD-05-A03-P01`；只增加 PROJECT Evidence 创建的受控前端传输客户端。|
|输入基线|冻结 `/api/v1/projects/{project_id}/evidence`，HND-05-A02 前置、CR-EXEC-002、已验 GLOBAL Evidence 客户端；不改 API/Schema/权限。|
|前置任务|后端 `create_evidence_create_router` 已有 PROJECT POST，Windows 写组合已装配；`ProjectEvidenceListView` 仅只读/资格，无创建入口。|
|涉及模块/实体/API|前端 SessionClient 与 Evidence 客户端；Evidence CANDIDATE、固定 Project DocumentVersion；既有 POST，暂只支持整文档 Locator。|
|权限|当前启用 PROJECT_MANAGER/IMPLEMENTATION_MEMBER 且可提交；后端逐事务重验项目/Session/License/来源，客户端不能自行赋予资格。|
|验收标准|严格请求/回执、项目 Location、CANDIDATE、私有 CSRF/原 Key、越权/畸形/不确定结果关闭；定向、前端完整回归/typecheck/build。|
|风险|本片无 UI、无当前 ELIGIBLE 资格，不能据此宣称 HND 版本可创建；真实浏览器/PG 与正式信任待后片。|

HND-05-A02 先前的 Capability 缺口已在 Windows 11 合成包内闭合，但 PROJECT Evidence 用户创建入口仍缺。依编码前检查停止 HND 版本页，转向此独立前置；不以来源缺失假问题或内部 UUID 大表单绕过。

Changed：增加 Session 私有 CSRF PROJECT Evidence POST 与严格 CANDIDATE 客户端，按当前项目角色预筛，逐字段核对原回执/项目 Location，错误与不确定结果关闭。Files：`apps/frontend/src/modules/auth/api/sessionClient.ts`、`apps/frontend/src/modules/evidence/api/projectEvidenceCreateClient.ts` 及测试。Migration/API：无 Schema 或后端 API 变更，沿用冻结 POST。Tests：首次全量 4 失败（客户端 UUID 正则写短），修正后定向 4/4、完整 1957/1957、typecheck/build 退出 0。Result：`EVD_05_A03_P01_FRONTEND_CLIENT_PASS`。Known Issues：尚无项目 Evidence 创建页面/真实 HTTPS、PG、人工资格或正式信任；客户端通过不等于 HND 版本入口可用。Next：`EVD-05-A03-P02` 安全选择同项目固定 DocumentVersion 并建立整文档 CANDIDATE 的页面，独立验证后再做包内链。
