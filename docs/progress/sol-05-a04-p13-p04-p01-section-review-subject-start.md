# SOL-05-A04-P13-P04-P01：Section Review START Subject Owner

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`INTERNAL_START_PASS / ENTRY_NOT_WIRED`。

编码前检查：Phase 2；输入为 Gate 2 冻结 DM-05/API-04、CR-SOL-024、Section 最新 DRAFT 六维现况证明 P13-P02、0183/0184 结果闭合状态 Guard；前置均满足。本片仅改 Solution 应用/持久层，实体为 Section/SectionVersion/Review 状态结果；不改公开 API、Schema、角色或 License。验收为精确最新版本、同事务六维复核、固定指纹、1～N 当前合格 Reviewer 的准备与 START 结果持久化、错误拒绝及 Windows 11/PG18.6 隔离验证。风险是并发升版、历史批准指针不一致、Review/Round/指纹不匹配；先取得 Outline→Section→Version 排他锁并复用 0184 结果闭合 Guard。

新增 `SOL-05`/`SOLUTION_SECTION_ALL_V1` Subject Owner：创建资格只接受最新无 Review 的 DRAFT；提交准备重验当前六维，返回统一 Review Engine 的固定内容指纹和受约束 Reviewer；统一 Engine 创建 Review/Round/快照后才将 SectionVersion 改为 IN_REVIEW、写不可变 START 结果。回放重新核对历史身份与当前可访问性。终态回调暂时失败关闭，不将送审或合成测试当作客户批准。

新增 SQL Repository 对父 Outline、Section、版本按创建流程一致顺序加锁，核对当前批准指针与历史，防止并发升版及旧指针；实际 START 更新/结果在调用方事务内提交。Windows 11/一次性 PostgreSQL 18.6 测试在合成 Review/Round/快照上执行真实 Repository START 与 0184 Guard，确认持久 IN_REVIEW、单条 START 结果，错误 Project 隔离；这不是正式客户确认或完整 Session/HTTP 链。定向 33/33、后端全量 3946 通过/3 跳过/6074 子例。

兼容/回滚：无 Migration/API/数据迁移；撤未装配内部 Owner/Repository 即可回滚代码。已有 Review 历史不得删除；此片本身不对用户开放入口。下一片 `P13-P04-P02` 接 ProjectManager/Session/License/幂等提交服务，随后 HTTP/Windows 端到端与终态独立验收。Gate 3、Pilot、Release 均未通过。
