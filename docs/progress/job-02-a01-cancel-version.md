# JOB-02-A01：原取消事务的用户版本条件

2026-09-27 / Phase2 / INTERNAL_PASS；输入0043、原Audit取消授权/首请求来源/持久收据，冻结API-01/03保留。编码前检查及偏差方案已先登记CR-JOB-003和DEC-265。

Changed/Files：Jobs AuditExportCancelFacts增加严格非负bigint lock_version，owned锁查询populate_existing刷新数据库触发器版本；Audit RequestAuditExportCancel末尾可选expected_version，显式版本加入原operation指纹，None保留原内部指纹。新命令在原Root/pair/Job锁与当前授权后比较实际version；原已完成收据先重放首次响应、当前授权再检查。冲突VERSION_CONFLICT整事务回滚，不完成收据，不写取消/Audit。无需新Schema、Migration、API路径、权限、依赖；未来HTTP必须显式版本，无None回退。

Tests：Windows11/Python3.13.15/本机隔离PostgreSQL18；新增5单位行为、全后端1160项无失败（2既有权限环境跳过）。实际validation/job-02-a01-cancel-version/verify.py两Scope验证：真实Submit PENDING v0→即时取消CANCELLED v2，同UOW读实际[0,2]；真实claim RUNNING v1→请求v2→受控Worker当前临时Vault身份确认CANCELLED v3；同Key双并发仅一次USER Audit/原首次receipt，确认后原版本/原Key重放返回原CANCEL_REQUESTED且十表无写；异Key同版本竞争一成功一VERSION_CONFLICT，仅一次请求Audit；真实发布成功v2后旧版本拒绝、当前版本只CHECKED且不改Job/result。

过期新Key、同Key不同version/None、旧None收据改显式version均拒绝且十表无写；旧None首次收据完整重放兼容。当前CSRF与License拒绝、实际Audit插入后故障，Job/审计/收据等十表完全回滚。原cancel-request、Worker cancel-confirm、expired-cancel三个真实验证均通过，并分别包含原publication双Scope空/260行真实文件/当前权限/Lease/取消-发布锁竞争及失败回滚。未绕原授权/首来源/Worker fencing。

开发wheel：645334 bytes，SHA256 `c65bbe357341c20492598e264ba55d12fe05215519b5cdaf172dd931a7c89a7f`；不是可交付完整安装包。此轮验证无失败；读取时曾使用不存在的无modules路径/PowerShell通配路径，定位后修正，未改变代码/测试验收。

Compatibility/Upgrade：需前序0043；无本轮迁移或生产操作，旧内部调用与指纹保留。Rollback撤版本调用/逻辑保留旧历史，不改原冻结提交。Known Issues：正式发行信任材料仍未供给；正向License明确合成，Worker使用临时实际Vault，非正式账户/监听服务/UI/20并发/其他平台/完整Scope/Gate证明。公开取消HTTP、JobId到Owner资源受权解析和完整JobView首次结果仍待；旧内部取消入口None不等公共权限。

Next：JOB-02-A02，JobId受权Owner取消路由前置（只支持显式Audit Owner绑定、无未知Owner回退），然后单独实现冻结项目/admin :cancel HTTP的强If-Match/CSRF/持久幂等与Windows写组合。Document及其他Owner/列表/重试不删范围。
