# JOB-01-A03：Windows显式任务详情装配

2026-09-27/Phase2；编码前输入ab15e99、CR-JOB-001/002、0043，A01内部和A02可选GET真实PG/HTTP通过。单问题：在已有--platform/--platform-write组合根显式接通原Jobs读取/原Audit Owner/真实License Guard，默认/login-only仍关闭，不新增Web写接口或密钥回退。

涉及Jobs/Audit/Project公开Application Port，实体与Schema不变；API原项目/admin GET，权限不扩大。验收：两Windows工厂真实PG/Session/项目及Admin读取RUNNING/SUCCEEDED/真实vN与原Result、安全404/401/License403、六业务表无写；默认/login-only404；装配任何构造错误静态失败不发布半装配应用，实际正式信任源不可用时拒绝启动/数据库释放。明确测试配置/License/cursor注入不当正式来源。

风险：只绑定Audit首个Owner，Document/其他Owner仍待；既有Compose来源前置仍需要供给，不能以此关闭发行Gate。回滚撤新Factory接线与import，保原可选Router/内部读取/0043；无本轮Migration/依赖/升级。先记录，后实施及真实验证追加。

实施：production_login.py在include_secret_read显式分支（--platform和--platform-write共有）组装实际AuthorizedJobReadService/SqlAlchemyJobReadRepository/ProjectAuthorizationService与AuditJobReadProjection，使用原licenses.guard、原当前Auth读Port和实际Audit Root/Acceptance/Result及Jobs pair Port；默认/login-only job_detail_router=None，未添加宽松回退。

验证：validation/job-01-a03-windows/verify.py实际PG18/当前Session/PM/Admin/原Worker发布，两个生产Factory通过ASGI读取双ScopeRUNNING v1/SUCCEEDED v2/原结果逻辑引用、每正读取六业务表无写；未知Session401、License拒绝403、Admin跨项目404，默认及login-only404。每工厂4新装配构造失败均静态拒绝、不发布半装配应用；撤测试License/来源注入后实际原Windows信任装配不可用，两工厂拒绝启动且六业务表不变。正向数据库来源/License/cursor/write材料明确注入，不是正式凭据恢复验收或监听进程/UI测试。旧Windows导出metadata/content（260行/摘要/来源/腐坏拒绝）及原发布回归通过。

Changed/Files：production_login.py、windows验证脚本、本进度/Contract增量/CR/决策/状态/版本。Migration/API路径/依赖/角色无变化；需前序0043和原目标账户材料。Tests：后端与构建最终结果后追加，未把未完成的正式供给当PASS。Result：已验组合INTERNAL_PASS，其他Owner/列表/取消/重试/正式材料/浏览器/三平台/完整Scope/Gate/安装包待。Next：AUD-03-A07公开导出POST，复用已验同事务幂等提交且202 JobRef.status_url使用已接线Jobs详情，先记录严格入参/许可/CSRF/安全映射。

最终测试/构建：后端1150无失败/2既有权限跳过；开发wheel642528 bytes，SHA256 `2b01a3b95e09ec2fd02fed9b218f3c39d77599d2966fe8325822fae34a6c7dbf`，仅开发构建不作为可用完整安装包。文档首次补丁因Contract目标行不匹配拒绝且未写入，核对文件后按独立有效上下文重试；产品/验收未因该编辑错误改动。
