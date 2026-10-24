# EVD-05-A03-P03：项目 Evidence 创建 Windows 11 非发行包验收

日期：2026-10-25；状态：`PRECHECK_PASS / VALIDATION_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `EVD-05-A03-P03`；只验收 P02 项目 Evidence 用户路径与资格，不改变产品合同。|
|输入基线|CR-EXEC-002、P01/P02 前端回归、固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。|
|前置|干净提交、重建后端 wheel/前端 dist、父包/pgvector 摘要复核；仅新非发行候选可证明新页面。|
|涉及模块/实体/API|PROJECT DocumentVersion、Evidence CANDIDATE/ELIGIBLE、Audit/幂等收据，既有 `/api/v1/projects/{project_id}/evidence` 与资格路由。|
|权限|一次性合成 ProjectManager/ImplementationMember/CustomerManager、License、TLS；创建与资格按既有角色分别重验，真实客户确认另行验收。|
|验收|候选全件 Hash/清洁解包；Edge 选同项目固定版本创建整文档候选、只读回读，HTTPS 当前有权人员资格核定，PG 固定引用/指纹/Audit/收据，匿名/错项目拒绝及资源清理。|
|风险|此项不提供页段精确定位，不宣称真人资格、正式信任/安装/UAT/Gate/Pilot 或 Server 2025/Debian 13；大 ZIP 只保存在本机忽略区。|

结果待实际运行填写，不预填 PASS。
