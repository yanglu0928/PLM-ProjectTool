# JOB-01-A01：通用任务详情实施前置

2026-09-27，Phase2；输入冻结API-03 JOB_PROJECT_GET/JOB_ADMIN_GET、DM04 JOB-01、实际Jobs ORM与Auth/Project安全Port。编码前核查，仅设计/前置不宣称接口已可用。

## 实际缺口

- Jobs现有application目录只有enqueue/claim/Lease/取消与证明，没有对用户的JobView查询Service/API Router；Audit结果GET已挂载，但仅成功导出制品，不能替代任务状态查询。
- API-01长任务202要求JobId/state/status_url。Audit `submit_export.py`具备事务幂等、原响应引用、Job/Outbox/Audit原子提交，尚无提交POST接线；`production_login.py`现仅读取/下载组合，不据内部测试声称浏览器链通。
- `JobRow`有actor_ref/scope/project/state/attempt/times，包含内部payload/fencing/lease，不能序列化ORM；没有资源lock_version。取消的If-Match必须另做可追溯版本方案及所有写路径验证，不把fencing_token当用户版本，不让POST无条件执行。只读详情可以独立实现，未来版本变化若影响冻结合同先登记CR。

## JOB-01-A01编码前检查与计划

当前Phase：2。当前WBS：通用Job详情内部Service/Repository/安全DTO（不同时做列表/写HTTP）。输入基线：API-03/Gate2冻结、既有Auth与Project Port。前置：Jobs实体/实际授权Port可用；原有界后台完成子任务不等于Gate3。

涉及模块：Jobs为唯一Job数据Owner，调用Auth/Project/License公开Port。实体：JOB-01只读，Owner提供安全result/progress/retryability，不直接读Audit/Document表。API：本子任务不挂载；后续按原GET路径显式可选。权限：PROJECT当前成员/角色与原actor资源再授权；PM/IM与其他角色仅自身可见仍遵守Owner敏感资源策略；DEPLOYMENT/GLOBAL仅当前Admin，Admin不能跨项目绕过成员检查。Audit导出正文权限不能被IM任务元数据权限扩大。

验收标准：严格UUID/32字节Session/trace，License+当前Auth+Project+Owner权限，跨项目/不存在同外部语义，停用/撤权拒绝；Job安全投影不含payload/Lease/fencing/路径/worker/Secret/traceback。只读无业务写入，故障脱敏失败。真实隔离PG双Scope状态/权限矩阵以及Owner不可用拒绝；后续HTTP happy/validation/异常/会话/隔离另验。

风险：通用Owner Registry必须显式绑定策略，未知Owner/type不能退化成“所有成员读所有任务”；progress/result/retryable不从payload或泛化状态猜测。首个Audit Owner实现后仍保留Document及其他Owner接线任务，不缩减Scope。ETag需要表示实际可验证版本，不伪造任意常数；版本设计按需另CR/迁移，保原冻结64cdf09。

实施顺序：A01内部只读详情（含显式Owner安全策略）→A02可选GET契约/真实PG→A03Windows装配→AUD导出POST（复用真实事务提交与JobRef）。Schema/API/权限发现冲突先CR，不直接挂上未经授权Repository。

【待确认】问题：正式公钥/目标账户来源未供给。影响：正式客户部署仍不能启动受许可业务。可选方案：继续合成验证独立实现，正式材料仍由受控仪式供给。建议：继续内部GET，不引入测试回退。是否阻塞：不阻塞独立开发，阻塞正式交付验收。没有新增人工业务事实/外发授权。
