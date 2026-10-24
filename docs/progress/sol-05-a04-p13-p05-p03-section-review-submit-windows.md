# SOL-05-A04-P13-P05-P03：Win11/PG18 Section 真实送审链

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_SYNTHETIC_END_TO_END_PASS / CUSTOMER_TERMINAL_PENDING`。

编码前检查：Phase 2；输入 Gate 2 API-04、CR-SOL-024、P13-P02 六维现时证明、0183/0184 Guard、P13-P04 Owner/提交服务及 P13-P05-P01/P02 HTTP/Windows 组合，前置满足。此片仅增加 Windows 11/一次性 PostgreSQL 18.6 验证脚本，不改业务代码/API/Schema/权限。验收为真实 Session/ProjectManager、合成客户成员、六维现时来源、Trace 撤销与恢复、同事务 Review/Round/固定快照/Section START、幂等重放、跨项目/非客户拒绝、数据库结果/收据/Audit。风险为合成账户被误当真实客户签署、旧 VALIDATE 回执替代现况、试验库越界；脚本使用临时本地数据库并在退出后关闭清理。

测试复用已有合成项目、批准 Spec 与 Section 作者适配依据，创建合成 `CUSTOMER_MEMBER`（仅测试数据）。先证明无有效 `IMPLEMENTS` 时 HTTP 422；创建后撤销，新的送审仍 422；重新创建有效覆盖后，项目负责人真实 Session/CSRF/License/项目授权下 HTTP 201，第二次同 Key 返回完全相同固定结果。指定项目负责人为“客户确认人”被拒 422，错误 ProjectId 404。SQL 检查精确版本为 `IN_REVIEW`、Review/Round 双引用与响应一致，START 结果、提交收据及 `REVIEW_STARTED` Audit 各恰好一条。验证脚本 exit 0，测试过程中没有对外 AI 调用或真实客户数据。

此前 P13-P05-P02 后端全量 3964 通过/3 跳过/6079 子例；此片只增加独立 PG 验收脚本，未重新运行全量。兼容/升级/回滚：无业务代码或 Migration，移除脚本不影响应用。此 PASS 只证明受控合成环境下送审；客户真实决定的 APPROVED/RETURNED/WITHDRAWN Owner、前端、正式信任、Gate 3、Pilot/Release 均未完成。
