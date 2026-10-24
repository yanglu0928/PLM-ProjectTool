# Survey 定义五个普通写命令 HTTP V1 增量

日期：2026-10-06。实现基线：冻结 API-01/API-04、Schema0106 和 CR-SUR-001/004；不增加或改名 Operation。

## 公共边界

Router 只通过 `create_app(survey_command_router=...)` 显式注入；默认应用五个路径均为 404。A05-A04 不进入 Windows 生产组合，真实组合与 HTTP/PostgreSQL 全链验证留给 A05-A07。

所有命令要求可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token` 和有效 License；项目角色、资源隔离及当前来源/部门资格继续由 Application Owner 在事务内重验。创建、归档、版本创建和校验要求 16～128 字符可打印 ASCII `Idempotency-Key`；修改、归档和版本创建要求强 `If-Match: "v<n>"`。

JSON 只接受 UTF-8 `application/json`，拒绝重复键、未知字段、NaN/Infinity、多余 query 和超过 2 MiB 正文。ID 必须是 canonical lowercase non-zero UUID。响应均为冻结 `data/trace_id` Envelope、`Cache-Control: no-store`，不投影内部表、跨模块正文/路径、异常或 Secret。

## Operation

|Operation|请求|成功|
|---|---|---|
|`SURVEY_CREATE` `POST /api/v1/projects/{project_id}/surveys`|精确 `name`|201 ACTIVE identity、ETag、Location|
|`SURVEY_PATCH` `PATCH .../{survey_id}`|精确 `name`，强 If-Match|200 SurveyView + 新 ETag|
|`SURVEY_ARCHIVE` `POST .../{survey_id}:archive`|空正文，强 If-Match，幂等键|200 ARCHIVED SurveyView + 新 ETag|
|`SURVEY_VERSION_CREATE` `POST .../{survey_id}/versions`|强 If-Match；完整 `questions[]` 和 `target_department_ids[]` 快照|201 DRAFT Version、内容指纹、Survey 新 ETag、Location|
|`SURVEY_VERSION_VALIDATE` `POST .../{survey_version_id}:validate`|空正文、幂等键|200 当前问题/条件/来源/目标部门报告，不改正式状态|

`QuestionInput` 精确字段为 `question_id/topic/question_text/objective/answer_type/validation_rule/required/condition_rule/expected_output/evidence_required/options/sources`；option 为精确 `option_code/label/description`。source 必须显式携带 `source_kind`、Handover/Capability/Template 三组类型化固定 UUID 字段和 `manual_source_note`，未使用字段为 `null`；业务 Owner 仍强制四类互斥形状、Project Scope 和当前资格。

## 错误、兼容与回滚

权限或资源隔离失败对资源统一 404；License 403；缺 If-Match 428；版本/状态/幂等冲突 409；字段、来源或部门资格问题 422；未知内部失败 503。冻结码表尚无独立的 Survey 定义来源/目标部门码，因此只对外安全投影 `VALIDATION_FAILED`，不增加未冻结公开码。

本增量无 Schema/Migration/依赖/配置/网络/外发。回滚方式是不注入 Router；已由 Application Owner 写入的合法业务历史不删除。原子送审、四个读取 Router 与 Windows 组合仍分别由 A05-A05～A07 完成。
