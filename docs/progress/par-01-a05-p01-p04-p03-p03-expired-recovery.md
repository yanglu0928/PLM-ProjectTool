# PAR-01-A05-P01-P04-P03-P03 Parser 取消过期恢复

日期：2026-09-30；Phase 2；编码前检查完成；Windows 11 内部验证 PASS。

当前 WBS：为 `CANCEL_REQUESTED` 且 Worker 未在租约内确认的 Parser Job 提供数据库到期恢复与提交确认丢失后的原源核验。输入 Gate 2 冻结 Job/Outbox、ADR-007 协作取消、CR-PAR-001/002、已验用户申请 P03-P02 和活代 P04-P02。前置满足，Gate 3 未通过。涉及 Jobs 当前 Job/Lease/Attempt、Document 当前 ParseRecord、Audit USER 首申请/SYSTEM 完成事件和 Parser 编排；不改公开 API、Schema、权限或依赖。

验收：仅当前 `document/DOCUMENT_PARSE` 代且数据库真实租约到期、原 USER 申请与当前 Job 历史一致时，按原 Job/Outbox/Document 来源将 RUNNING ParseRecord（如有）置 CANCELLED、Lease→EXPIRED、Attempt.error=JOB_CANCELLED、Job→CANCELLED 并附最小 SYSTEM Audit，同事务提交；无 ParseRecord 不伪造。未到期、旧代/其他 Worker/其他 Owner、缺失或重复首申请、错误来源均零写；Audit/Document/Jobs 后置故障回滚；提交回执不确定时以同一终态的 Job/Lease/Attempt/Document 和唯一 SYSTEM Audit 只读核验，不再次写。恢复不宣称旧进程已被杀，旧进程后续发布由 fencing 拒绝。

风险/回滚：仅靠进程状态会误判；选择数据库 `clock_timestamp()` 与行锁作真源，候选扫描只给 hint，实际恢复再严格锁定。历史终态不可撤，回退应用时停恢复入口并保留历史。正式 SystemActor 身份、独立 Worker 循环和三平台运行仍另验，不以合成身份推定生产可信。

实现与验证：Jobs 新增当前代过期核验/终态确认只读证明，Document 新增当前 ParseRecord 只读终态证明，Audit 新增唯一 SYSTEM 恢复事件证明；Parser 编排复核 Job/Outbox、已提交上传和原 USER 取消 Audit，在同 UOW 内收口 `EXPIRED/CANCELLED`。`validation/par-01-a05-p01-p04-p03-p03-expired-recovery/verify.py` 用真实 PostgreSQL 18、实际提交的合成文件和 HTTP 用户取消验证：活租约、外来 Worker/错误代数零写拒绝；真实到期且无记录/有 RUNNING 记录两种路径；Audit 注入失败和 Document 后末端 Job 失败整笔回滚；唯一恢复事件、确认丢失只读复验和旧代重放拒绝。Python 3.13 后端全量 1635（3 既有跳过）、backend wheel PASS；本地数据库是隔离夹具，未迁移生产。

边界：此项提供可调用的恢复步骤，不等于独立 Worker 调度、生产 SystemActor 或崩溃进程强杀已实现。既有 publish/heartbeat checkpoint 会拒绝过期与已终止代；独立进程主动扫描/调用仍列后续 WBS。未改变 `/api/v1`、Schema 0050、ORM、依赖和权限。回滚代码时停用恢复编排，已提交 Audit/Job/ParseRecord 历史保持原样。
