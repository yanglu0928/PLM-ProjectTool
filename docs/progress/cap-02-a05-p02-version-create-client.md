# CAP-02-A05-P02：标准能力版本创建命令客户端

日期：2026-10-24；状态：`FRONTEND_COMMAND_PASS / USER_FORM_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `CAP-02-A05-P02`；只增加版本 POST 命令客户端及 DTO/回执测试。|
|输入基线|Gate 2 冻结 `/api/v1`、`CR-EXEC-002`、既有 Capability Version POST 合同；`CAP-02-A05-P01` 拆项。|
|前置|GLOBAL 固定文档/基线身份、Evidence 候选及创建拒绝矩阵包内验收已通过；正式 ELIGIBLE 与版本批准仍未形成。|
|模块/实体/API|前端 Capability Version 命令客户端、私有 Session CSRF 桥；`POST /api/v1/global/capability-baselines/{baseline_id}/versions`；无 ORM、Migration 或后端 API 变更。|
|权限|只允许当前已登录的 DeploymentAdmin 发送，仍由后端现时复核 Session/角色/License/来源及 Evidence 资格。|
|验收|完整条目 DTO、固定 Document/Evidence 引用、基线 `If-Match`、原 Idempotency-Key、严格 DRAFT/201/ETag/Location 回执与拒绝/不确定结果映射；定向和全量前端回归。|
|风险|客户端不能替代后端同源/ELIGIBLE 核验；写入后仅 DRAFT。调用超时或响应不明必须保留原操作号，不能创建第二版本。|

新增 `CapabilityVersionCreateClient` 及限定的 Session 命令路径，不暴露 CSRF。客户端检查 1～500 条条目、稳定 ID/代码唯一、必填文本、固定文档与 Evidence 非空/去重、状态枚举；服务端继续实施权威同源和资格验证。回执严格限定版本 ID、基线 ID、`DRAFT`、来源摘要、内容指纹、时间、基线 ETag 从 vN 到 vN+1、201、Location 和 no-store。已知服务端权限/资格/版本/幂等错误按契约映射，未知响应或网络中断标记不确定，不自动换 Key。

验证：定向 5/5；前端全量 171 文件、1917/1917，typecheck 和 Vite build 通过。构建有既存大分块提示，不作为本项失败。未增加用户编辑页、没有执行版本写入，也没有批准或正式信任事实；下一项 `CAP-02-A05-P03` 建立从当前 GLOBAL 固定文档与 ELIGIBLE Evidence 选取的条目编辑页，再做包内 Edge/PG 验收。正式安装、UAT/Gate/Pilot/发行继续未通过。
