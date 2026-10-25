# SOL-05-A04-P13-P03-P02：Section Review 状态与批准指针窄门

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`SCHEMA_GUARD_PASS / APPLICATION_NOT_WIRED`。

编码前检查：Phase 2；WBS `SOL-05-A04-P13-P03-P02`；输入为冻结 DM-05/API-04、CR-SOL-024、DEC-1208 与已验0183；前置P13-P02现时六维只读证明及P13-P03-P01封闭结果表已完成。涉及Solution SectionVersion/Section根、统一Review事实读与数据库状态结果；无公开API或权限新增。验收为同事务合法状态边、Review/Round/内容快照精确绑定、不可变结果闭合、非法DML拒绝、空/旧数据升降、drift及全量回归。风险为裸状态/指针更新、并发升版或伪造旧评审结果，验证前不得装配应用入口。

0184保留原0160/0148函数及其INSERT/DELETE职责，仅将SectionVersion UPDATE与Section指针UPDATE改由专用窄门处理；SectionVersion INSERT增加“最新仍在评审则拒新版本”保护。仅允许`DRAFT→IN_REVIEW→APPROVED/RETURNED`、旧`APPROVED→SUPERSEDED`；指针仅可递增锁版本后指向同Section已批准版本。新增结果触发器核对同Project、最新固定版本、精确Review/Round/政策`SOLUTION_SECTION_ALL_V1`、内容指纹快照、终态事件和先前批准版；延迟闭合触发器要求状态/指针变化在同事务有不可变结果。批准版唯一索引阻止同Section双批准。原固定内容、Spec声明与创建首次结果仍不可变。

Windows 11/一次性PostgreSQL 18.6：空库0184升降重升及已有Section史升级；合成Review行仅作数据库Guard隔离验收（非真实客户确认），START、APPROVED、RETURNED、SUPERSEDED四状态路径与指针通过；缺结果直接更新、未批准指针、错误内容指纹、结果改写、有历史回降均拒绝；head ORM drift无新增操作，脚本exit0。后端全量`3941 passed, 3 skipped, 6074 subtests`。P13-P04仍须由正常授权/Review Engine/当前六维事实同事务写入，测试合成事实不得算正式Review、Gate或Pilot通过。
