# HND-05-A03-P01：交接版本校验前端安全客户端

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / PACKAGED_BROWSER_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A03-P01`；只接入冻结的 Handover Version `:validate` 命令客户端，不做送审/Reviewer 页面。|
|输入基线|Gate 2 冻结 API、`docs/api-contract/handover-command-v1-increment.md`、P04 包内 DRAFT 创建通过。无 API/Schema/权限改动。|
|前置|已有 Handover Version 只读 DTO、项目角色会话、Backend 生产组合校验 Router 和独立已验的 DRAFT；正式信任缺口不阻断安全客户端合同。|
|实体/API|`POST /api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/{version_id}:validate`，空正文、私有 CSRF/Origin、16～128 字符幂等 Key；200 报告与 Audit，不改版本状态。|
|权限/风险|项目负责人或实施成员可校验，后端重验项目授权/License/当前来源与资格；前端不把 `valid=true` 当批准、客户确认或后续送审成功。未知响应保留原号，用户须核对审计再重试。|
|验收|定向覆盖空正文/Key/角色预筛、完整报告、阻断码/无告警/时间/计数和不可信回执、401/403/404/409/422/503及网络未知态；前端全量测试/typecheck/build。Edge/HTTPS/PG、送审与包内仍留独立任务。|

编码前条件满足。此任务不改冻结合同；若源码与合同冲突，停止该片并先记录偏差。

实施：`SessionClient` 增加冻结 Handover Version 校验的私有空正文 POST，仍用当前
CSRF、可信同源浏览器会话、原 `Idempotency-Key`、超时和未知结果安全态；客户端仅允许
当前项目负责人/实施成员预筛，严格核对版本身份、声明计数、七类有序阻断码、空 warnings、
Audit 引用和 UTC 时间。报告 `valid=true` 只是本次来源与完整性通过，不改变 DRAFT
状态，不代表送审、客户确认或 Reviewer 批准；服务端仍为权限/License/当前来源最终权威。

验证：定向13项（含六类 HTTP 错误、矛盾/无序阻断报告）；前端全量185文件1987项
退出0。首次构建因 `unknown` 数组在闭包内未被 TypeScript 保持收窄而失败，仅修正
读取前一阻断码时的显式类型断言；补齐负例后定向13、全量1987、typecheck/生产构建
再跑退出0。无 API/Schema/数据迁移，回退前端客户端/传输方法不删除
Audit 历史。页面入口、真实 Edge/HTTPS/PG、包内校验及送审均未在本片验收；
Next：`HND-05-A03-P02` 将校验报告接入交接详情页，保留原操作号/阻断码并明确非批准。
