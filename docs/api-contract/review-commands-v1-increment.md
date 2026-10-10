# Review 写命令 HTTP 增量合同 V1

日期：2026-10-05；WBS：`HND-01-A04-A02-P03`；来源：Gate 2 冻结 API-01/API-02、DM-05、CR-HND-001/002/004。本文只细化冻结的四个 Review 写端点，不改路径、角色、Scope、License、CSRF、幂等或 If-Match 控制。

## 共同边界

- Router 只有显式注入时存在；默认应用保持404。当前只有`HND-02`注册真实 Subject Owner，未知`resource_type`不使用通用成功处理。
- 请求必须有受信 Origin/Host、当前 Cookie Session、`X-CSRF-Token`和16～128字符可打印 ASCII `Idempotency-Key`；禁止 query，只接受单一 UTF-8 `application/json`，上限2 MiB，拒绝重复/unknown字段和非标准数值。
- 开轮和撤回要求单一强`If-Match: "v<n>"`；决定不新增冻结合同未要求的 If-Match。成功响应使用`data/trace_id`、`Cache-Control: no-store`和当前 Review ETag，不返回主题正文、内部 Owner/SQL 名称或异常。

## 严格 DTO

|Operation|请求正文|成功结果|
|---|---|---|
|`REVIEW_CREATE`|`subject_ref` 精确包含`resource_type/resource_id/version_id`|201；Review identity、固定Subject、policy、`DRAFT`、空active round、`"v0"`、创建人/时间及Location|
|`REVIEW_START_ROUND`|`subject_version_ref/reviewer_user_ids/policy_code`|201；Round identity、固定Version、Reviewer、policy、`IN_REVIEW`、round no、Review ETag、发起人/时间及Location|
|`REVIEW_DECIDE`|`decision/comment`；decision仅`APPROVE/RETURN`，RETURN必须实质comment|200；Assignment已决定、Decision identity、Review/Round聚合状态与两层ETag|
|`REVIEW_WITHDRAW`|`reason`字符串或null|200；`WITHDRAWN`、Review/Round identity、固定Version、两层ETag和事件时间|

`project_id/review_id/review_round_id`仅来自路径，Actor仅来自Session；客户端不能传`owner_module`、Actor、Scope、Project或内部状态。Create回显的`version_id`是本次创建指令已由Owner绑定的固定版本，不由可变状态重建。

## 错误与组合前置

无权/未知资源404，License/CSRF 403，缺If-Match 428，版本/状态/幂等/Subject锁/重复Decision 409，Reviewer无资格/退回缺意见/输入问题422，未知运行故障503。本项已将API-02冻结的四个`REVIEW_*`错误码注册到统一错误包。

Windows生产组合必须在同一runtime/UOW中装配Review create/start/transition仓储、当前Session访问、Project授权/Reviewer资格、License、Audit、收据及唯一`HND-02`Owner；只在`--platform-write`挂载。读取模式不得因存在POST Router而开放写入。本项未完成该组合或真实HTTP/PG链，留给P04验证。
