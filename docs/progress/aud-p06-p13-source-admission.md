# P06-P13-P03-A02：明确坏来源准入与后台接线

2026-09-27/Phase2，CR-AUD-005/P03-A01。编码前：Audit准入/Step/Loop、Jobs既有scan、Audit原源校验；无权限/API/Schema/依赖变化。原claim_next默认语义保留，后台显式isolate_sources=True，严格bool与实例互斥；每次只处理一个候选，最多原3次真实死锁/eligibility重试。

游标仅在已完成只读拒绝UOW后前移，保一个常数大小cursor；正常claim或扫到当前末尾清游标，下次可回查修复来源。cursor不是排除名单/全队列空证明。明确格式坏引用、Root缺失/错绑定、Acceptance缺失/错绑定/真实审计源不一致、Jobs pair明确CONFLICT_STATE可返回技术SOURCE_REJECTED；其他异常/DB/identity失效/commit确认仍原失败关闭/恢复。坏Job/Lease/Attempt/Audit不写，不授正文/终态，最小诊断只固定拒绝数量，不输出payload。Loop拒绝时正常poll等待避免热循环，STOP和pending排空不改。

验收：单位矩阵验证每分类/无claim无commit、未知故障不吞/identity后验、旧入口和确认恢复保留；实际双Scope两坏ref后正常发布、坏行保原/无Attempt，缺Root/pair也验证。风险：广义不一致Lease/非明确领域故障仍失败关闭，不声称任意坏源都隔离；新版反向锁序deadlock/无限流量公平/正式材料/完整包/Gate待。回滚撤显式后台接线、新DTO分类保历史；无迁移升级。

结果 INTERNAL_SOURCE_SUBSET_PASS：原入口默认保留，新后台显式隔离、实例非阻塞锁和常数cursor，返回严格SOURCE_REJECTED DTO、Loop拒绝计数/poll，CLI仅固定数量诊断/不猜终态。六新unit覆盖格式/Root/Acceptance/pair明确分类、未知DB异常与identity后验不吞、isolated lost-ack确认、忙实例/非法flag、Loop后续执行和STOP；1125项后端通过（2既有权限跳过）。Acceptance原源明确错误通过专属内部reason_code分类，原对外AUDIT_UNAVAILABLE不变，防止新增错误码泄漏冻结API。

真实PG双Scope Loop跨格式错/零UUID两个坏head、ROOT_MISSING与PAIR_MISMATCH，每拒绝六表无写，坏Job PENDING/0Attempt，后续正常Job实际SUCCEEDED；恢复本轮合成来源后原任务发布。旧入口仍坏源失败关闭。原P06真实commit前回滚/commit后确认恢复、P12-B02真实Windows CLI子进程双Scope文件摘要/缺公钥及idle无写/外部active停止单次排空均回归通过。License明确测试替身，不提升正式授权结论。

开发wheel633740 bytes，SHA256 `64adf7401f856d2319882341ecf6e7857598ce2f300ec0371aa72217e4ebe3d4`；无Migration/API/依赖/升级。Acceptance审计源缺失真实PG故障矩阵、新锁序真实40P01、耗尽扫描坏源、复杂Lease不一致、长期优先级公平仍待，CR-AUD-005不关闭；完整Scope/正式材料/安装包/Gate待。下一P13-P04真实反向锁序deadlock/分类复验。
