# SOL-05-A04-P13-P04-P02：Section Review 内部提交服务

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`INTERNAL_SERVICE_PASS / HTTP_NOT_WIRED`。

编码前检查：Phase 2；输入为冻结 DM-05/API-04、CR-SOL-024 及已验 P13-P04-P01 START Owner；前置满足。涉及 Solution 提交应用服务、Project 操作权限映射、Review 内部编排与同事务幂等收据；Section/Review/Receipt 为已有实体。无新公开 API、Schema、License 权益。验收为 ProjectManager 才可提交，1～32 位不重复当前合格客户确认人，Review Engine 同事务取得 Section 当前六维证明与固定指纹、Review/Round/快照/Section START/收据/Audit 原子提交；重复请求返回原首次结果，错身份/跨项目/许可失败拒绝。风险为重复签署、跨项目和内部人员冒作客户；失败关闭、事务回滚及后续真实 PG/HTTP 分层验证。

新增 `SubmitSectionReview`/`SectionReviewSubmissionService`，传入固定 SectionId+VersionId，不靠客户端提供指纹或版本事实；许可、会话/CSRF、项目负责人权限、确认人锁与受控 Subject Owner 共同把关。IdempotencyKey 绑定项目/章节/版本/确认人/政策；重放只读取同项目原 Review/Round，并重新检查当前访问。三次仅对分类确认的 PostgreSQL 死锁重试；其他异常不重试、不返回凭据。提交前后检查 License。Project 操作新增 `SOL_SECTION_VERSION_SUBMIT_REVIEW` 仅 ProjectManager 写权限。

依据冻结“客户确认人”语义，将 Section START 的实际 Reviewer 资格限制为 `CUSTOMER_MANAGER`/`CUSTOMER_MEMBER`；项目内部角色仍可按原权限读取历史，但不得作为客户确认人。此为已批准规则的精确落实，不变更统一 Review Engine 或 SOL-06 策略。新增权限矩阵及服务单元测试，覆盖正常、回放、无效输入、许可、角色和错主体；P13-P04-P01 的 Win11/PG18.6 SQL START 证据仍有效。本片内部服务尚未由 Windows 组合或 HTTP 调用，故不能宣称真实 Session/PG 端到端通过；在下一片独立验收。

兼容/回滚：无 Migration/API/数据迁移；停止装配或撤内部服务与权限映射可回滚本片，评审历史仍应保留。Gate 3、Pilot、Release 与正式客户签署均未通过。
