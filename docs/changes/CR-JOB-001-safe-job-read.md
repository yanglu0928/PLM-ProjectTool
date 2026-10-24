# CR-JOB-001：任务只读装配与Owner安全投影

A03更新（2026-09-27）：Windows两显式platform工厂已组装实际Jobs读取与Audit Owner，正向合成信任/真实PG-Session-Worker两ScopeRUNNINGv1/SUCCEEDEDv2与原结果、401/403/Admin项目404/读取无写通过；默认/login404、每工厂四新构造失败及实际正式信任源不可用启动拒绝。旧导出下载/原发布回归通过。仍非其他Owner/完整Jobs/正式账户/浏览器/发行验收，CR-IN_PROGRESS；下一Audit公开提交POST。

2026-09-27 / IN_PROGRESS；Phase2，原冻结64cdf09不改。持续自主授权执行，来源JOB-01-A01前置。只实现冻结通用Jobs详情内部能力，不修改路径/角色Scope、不将内部Lease作为浏览器版本。

编码前：WBS JOB-01-A01；输入API-03与既有Job/Auth/Project；实体JOB-01只读，无Migration。涉及Jobs Service/DTO/Repo、Project新增JOB_PROJECT_GET只读锁定当前成员策略、Audit提供其任务原源绑定Port。正常Session/License、路径ProjectId、PM/IM或其他角色仅原actor，再叠加Owner策略。Audit仅返回任务元数据，不授导出正文/结果下载权限。

选择：Jobs先只读安全元数据，再调用显式Owner策略核验原资源与安全结果，最后同事务再次读取绑定，变化则静态失败；未知Owner/type拒绝，不遍历读取其他模块表。不选直接序列化ORM、解析payload输出、以Job状态猜retryable/result、UserId代Session授权。Audit策略从原Acceptance查原Root，核Job/actor/scope/pair与原结果，不直接跨模块SQL。首个Audit策略后Document和其他Owner仍需接线，不取消通用Scope。

风险：Owner内部锁序可能竞争，保原失败关闭，不加入无限重试；同事务Auth/Project锁保护撤权，Job无锁提示后Owner完整pair锁+最终快照一致性。只读不写Audit/Job，不掩盖坏来源为不存在以外业务事实。未知错误统一JOB_UNAVAILABLE；外部映射后续HTTP再验。当前子任务DTO不宣称完整JobView/ETag已可用，If-Match版本设计另记录，不能公开不完整合同。

验收：Unit权限/绑定/异常/严格DTO、真实PG双ScopePENDING与SUCCEEDED、来源不一致与跨项目/失效会话/停用/非Admin拒绝无业务写入。前置满足后编码，测试失败须保留说明。迁移/API/依赖无变；回滚撤只读Service/Port和新策略，不影响旧写路径，保原版本及文档；正式公钥/发行/Gate3待。

A01更新：内部Service/严格事实/Owner DTO、Jobs只读Repo、JOB_PROJECT_GET策略与实际Audit Owner Port已实现；1143无失败/2跳过，真实PG双ScopePENDING/RUNNING/SUCCEEDED与原Result、角色/原actor/跨项目/Admin/停用/未知Session/坏绑定拒绝六表无写，原发布回归通过。当前仅Audit Owner，非HTTP/完整JobView/ETag或正式部署PASS。初次测试构造边界与验证Worker属性错误在进度中保留；后续公开版本/Contract、Document及其他Owner、全Scope仍待，CR打开。

A02-P02更新：0043真实版本前置后新增可选双ScopeGET/安全JobView/强vN与no-store，默认404；1150无失败/2跳过，实际PG/原Auth-Project-Audit Owner通过ASGI 8授权/13拒绝矩阵、状态/版本/结果逻辑引用、六业务表只读与原发布通过，条件请求不绕撤权。无已验细分progress/checkpoint/error则null，Document/其他Owner、Windows装配/完整Job模块待，CR仍IN_PROGRESS。首次脚本成功数量门槛误填10而实际8已在进度保留和更正。
