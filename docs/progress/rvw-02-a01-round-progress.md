# RVW-02-A01 多人决定不可变进度规则

2026-09-26；0.1.0.dev0；CR-RVW-001；结果 DOMAIN_PASS。

## 编码前检查

Phase 2；WBS RVW-02-A01；输入冻结 DM-01/DM-02、AF-02、SC-02、API-02，以及 RVW-01-A01/CR-RVW-001 设计。前置已登记历史/主题锁/完整集合规则及风险；此纯领域任务不要求不存在的 Owner/Review Schema 已完成。范围仅 review Domain 与单测，实体为 Round owned progress/不可变 Decision/Withdrawal 值；不创建完整业务 ReviewRound、主题身份或客户事实。

无 API/权限/数据库/依赖/架构改变。实际 Session/License/客户确认人资格/Scope/Subject Owner 由后续应用检查，UUID 及枚举不是证明。验收为唯一 1～N ReviewerSet、每人一次决定、实质 RETURN、完整集合汇总、撤回历史/待处理保持、终态封口、不可变/UTC/跨轮拒绝。

## 实施与验收

新增 ReviewDecisionKind/ReviewRoundState、不可变 ReviewDecisionSnapshot/ReviewWithdrawalSnapshot/ReviewRoundProgress。记录决定返回新值，不覆盖旧意见；核对本轮 Assignment 形状，拒绝陌生 reviewer、跨轮、重复人/Decision ID。RETURN comment 非空且非 Unicode 纯空白/含 NUL；APPROVE 可不提供意见，不擅自新增公开长度上限。UTC 时间需不早于启动，撤回不能早于已存决定。

state 是从完整不可变集合派生而非客户端输入：有待处理人始终 IN_REVIEW，哪怕已有 RETURN；全完成后任一 RETURN→RETURNED，否则 APPROVED。撤回仅 IN_REVIEW，保留已决定及 pending 列表并封口；终态拒绝新决定/再撤回。PENDING 枚举保留冻结状态，但本 owned progress 从已开始的一轮出发，不实现半套开始接口或伪造 Subject 锁。

Windows 11/Python 3.13：新增 9 项单测 PASS，完整后端 681 项无失败（2 项既有符号链接环境跳过）。覆盖三人所有 8 种决定组合 × 6 种顺序的完整集合/中间态检查，一人即时汇总、重复/跨轮/陌生人、两个汇总终态、带 RETURN 的未完成撤回/保留历史、空/重复/可变 ReviewerSet、nested 绕过构造重验、Unicode 意见/可选 APPROVE/无新增长度约束、UUID/UTC/时间前后、不可变及安全异常。

开发 wheel 构建/包含 review Domain PASS；SHA-256 `a11cff73c52080d35cba574edceeee56fead6ec4ea60a80078eea6b4be057799`。非正式安装包。

## 兼容、风险与后续

无 Migration/API/依赖，数据库仍 0033；升级无需额外动作，应用可不使用新值对象回滚，无数据被改写。未运行 Review 数据库/实际权限/Owner/HTTP/覆盖率/性能；纯规则通过不代表 Review 服务/客户批准/Gate PASS。Server 2025 未验，Debian 13 暂不验证。

Next：RVW-01-A02 按八表设计实施 Review 持久层与增量迁移，真实数据库 Scope/完整轮次/状态与不可变保护验证；之后接受权 Owner/服务，不能直接挂公开接口。
