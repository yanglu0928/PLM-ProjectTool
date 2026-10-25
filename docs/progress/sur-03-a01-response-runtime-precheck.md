# SUR-03-A01：Assignment/Response 运行时前置核查

日期：2026-10-06。结论：`SUR_03_A01_RESPONSE_PRECHECK_PASS`。下一项：`SUR-03-A02` 实现 SRV-04 四表 ORM 与 Migration `20261006_0108`。

## 核查结果

- 冻结数据模型存在 SRV-04 `SurveyAssignment`，物理表固定为 `srv_assignments`、`srv_responses`、`srv_answers`、`srv_answer_evidence_refs`；冻结唯一索引要求同 Round target 使用 `NULLS NOT DISTINCT`。
- 冻结 API 有 Assignment list/create/get、Response record、Assignment submit/validate/return 七个 Operation；状态固定为 ASSIGNED、IN_PROGRESS、SUBMITTED、VALIDATED、RETURNED，更正必须追加，面对面录入必须为 FACILITATED_RECORD 并固定原始 PROJECT_RECORD Evidence。
- 当前运行实现为零，Alembic head 为0107。已有可复用边界包括：Round当前状态与source append、SurveyVersion固定Questions/Options/target departments、Evidence/Document固定证明、ProjectAuthorization、Session/CSRF/License、Audit与持久幂等。
- 冻结基线没有定义部门级Assignment、Response/Answer关系、RETURNED重提、typed JSON和Round完整性细节；已登记CR-SUR-008，选择单问题Response/一对一Answer、单根单后继更正链、RETURNED更正后重提，以及至少一项/全目标部门覆盖/全部VALIDATED的非空Round完整性。

## 边界

本项为编码前核查和可追溯设计记录，无程序、Schema、API、依赖、Secret、网络或数据外发变化；没有创建任何客户Assignment/Response，也未开放Round CLOSE。冻结URL/角色/状态/四表不变，具体实现分为A02～A09，防止跨状态机一次提交。
