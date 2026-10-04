# P06-P13-P06：有限混合队列持续循环

2026-09-27/Phase2，CR-AUD-005/P05前置通过。编码前：仅验证脚本，真实Jobs/Audit/文件原组合，无API/Schema/权限/依赖变化。目标是有限静态混合负载验收，不外推无限高优先级流量/全局性能。

每个Scope真实第三次到期坏来源、4个高优先普通坏来源、12个双Scope正常任务，同一真实Loop持续run（不是重复once）。按实际执行结果全正常完成才request_stop，真实STOPPED后静止关闭，核坏Job/Lease/Attempt原行、正常单Attempt/文件结果与SystemActor；恢复合成来源可正常发布，原第三代安全失败/确认丢失/旧字节保留。不删坏任务或猜终态，技术cursor常数内存。

Acceptance真实审计源被数据库不可变触发器保护，不关闭触发器伪造坏源。尝试本轮审计行UPDATE必须实际P0001拒绝且无写；专属来源分类故障分支仍以既有unit证据为准，不以保护测试冒充真实审计缺失修复。License替身仅测试、PG/Vault真实隔离；观察超时检查同一Future，不重启。回滚撤验证脚本，无迁移/升级，复杂Lease/预检竞态/真实质量/发行/Gate保留。

结果 FINITE_MIXED_COMPLETION_PASS / PERFORMANCE_NOT_PROVED：两轮（分别由PROJECT/DEPLOYMENT实际第三代到期fixture触发），每轮真实连续run完成12个双Scope健康任务，4个高优先普通坏来源+1个耗尽坏来源原Job/Lease/Attempt不变，实际STOPPED/所有句柄静止；恢复普通测试源后四任务实际完成，原第三代安全失败/actual commit-lost-ack/旧字节保留。每轮明确计数 `(steps=91,rejected=78,executed=12)`，原cursor仍常数内存。原发布并发/回滚fixture同次通过。

Acceptance请求Audit实际UPDATE被不可变trigger P0001拒绝、六表无写；未禁trigger/伪造真实source损坏，专属分类仅原unit证据，历史数据损坏仍fail closed/人工恢复，不能声称真实故障修复通过。无生产代码/API/Migration/依赖变化，未重跑未变unit/wheel（此前1130/2跳过保留）。

偏差证据：正常claim后清游标导致坏高优先head反复重扫，有限任务可达但每轮78拒绝。尚无生产性能PASS；下一P13-P07优化cursor回绕与反复拒绝开销，实施前记录语义/新任务可见性/STOP/确认恢复/回滚，不能静默改变业务优先级或以无限排除集隐藏坏任务。CR-AUD-005/正式材料/完整包/Gate仍待。
