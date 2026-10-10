# SUR-01-A03-P03：SurveyVersion Validate Owner

日期：2026-10-06

状态：`SUR_01_A03_P03_VERSION_VALIDATE_PASS`

完成 ProjectManager/ImplementationMember 内部验证 Owner：以共享锁重建不可变六表快照，复算内容指纹与声明计数，验证题型白名单、有界 ConditionRule、仅引用同版本较早问题及环路，并重新消费 Handover、Capability、TEMPLATE Document 与 Project Department 当前证明。完整报告固定问题/选项/来源/部门/条件数量及稳定 issue code；Audit、持久幂等收据和第二次 License Guard 位于同一事务。

同一 Key 返回首次审计报告，不因后续来源状态漂移而改写；新 Key 重新观察当前事实。本项不修改 Version、不新增 Migration、不开放 HTTP，也不导入或外发客户资料。

验证：新增定向 7 项；Windows 11/PostgreSQL 18.6 验证有效报告、来源失效、非法题型、未来引用、条件环、重放/冲突、Audit 回滚/恢复和四份回执；后端 2797 项通过/3 项跳过；wheel 1035 项，SHA-256 `e8491872dff06a1549721639940e0e7f7adb9ca7f3f125473935b8f243df2b64`。

下一项：`SUR-01-A04-A01` 核查统一 Review Subject、送审状态迁移、终态消费与批准指针更新前置条件。
