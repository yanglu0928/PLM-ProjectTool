# SUR-01-A05-A01：Survey 定义 HTTP 与读取 Owner 前置

日期：2026-10-06。结论：`SUR_01_A05_A01_DEFINITION_HTTP_PRECHECK_PASS`。下一项：`SUR-01-A05-A02` Survey/Version 读取 Owner 与有界分页。

## 冻结范围与现状

API-04冻结Survey定义共10个Operation：Survey LIST/CREATE/GET/PATCH/ARCHIVE，Version LIST/CREATE/GET/VALIDATE/SUBMIT_REVIEW。当前内部已有真实CREATE、VERSION_CREATE、VERSION_VALIDATE、`SRV-02` Review Subject/终态消费，并已开放通用Review四写生产组合；Survey专用公开Router数为0，读取Owner、Survey PATCH/ARCHIVE Owner和业务专用原子SUBMIT_REVIEW Service均为0。

P04完成的通用Review create/start两步端点不取代`SURVEY_VERSION_SUBMIT_REVIEW`。冻结API-04要求业务端点以ProjectManager身份固定SurveyVersion、评审人和`SURVEY_ALL_V1`，在同一业务编排内重验当前定义并创建/启动ReviewRound；前端不得以两次通用HTTP请求模拟该原子命令或暴露中间DRAFT Review。

## 实施分解

|WBS|唯一问题|验收边界|
|---|---|---|
|`SUR-01-A05-A02`|Survey/Version只读Owner与有界分页|四类Project成员、稳定游标、固定Version完整问题/选项/来源/部门投影、零业务写|
|`SUR-01-A05-A03`|Survey metadata PATCH/ARCHIVE Owner|ACTIVE、强ETag、双写角色/仅PM归档、IN_REVIEW栅栏、Audit/幂等和历史保留|
|`SUR-01-A05-A04`|CREATE/PATCH/ARCHIVE/VERSION_CREATE/VALIDATE五个普通写HTTP|严格DTO、最小投影、默认关闭，复用既有Owner|
|`SUR-01-A05-A05`|`SURVEY_VERSION_SUBMIT_REVIEW`原子业务编排|当前定义重验与Review create/start/收据/Audit同事务，不暴露中间Review|
|`SUR-01-A05-A06`|四读Router与Survey/Version游标|LIST/GET/Version安全白名单；不旁路Document/Evidence/其他来源Owner权限|
|`SUR-01-A05-A07`|Windows读/写组合与真实HTTP/PG|只读模式四GET，写模式全10 Operation，游标密钥缺失失败关闭|

## 约束与验证

- Survey PATCH只允许名称等冻结metadata，不直接修改正式指针、状态、Version内容或Review引用。Archive不删除历史，存在IN_REVIEW时不得静默绕过Review。
- Version GET固定返回不可变问题、选项、条件、来源类型化引用和目标部门引用；不得复制Document/Handover/Capability正文，也不得把TEMPLATE描述为客户事实。人工来源文本属于项目业务内容，仍受当前Project读取授权。
- LIST必须采用稳定、加密、会话/Project/page-size绑定游标；GET/Version GET使用强ETag与`Cache-Control: no-store`，未知/越权统一隐藏。
- 本项为静态交叉核查与实施拆分，无代码、Schema、配置、Secret、网络或数据外发；不将缺失Operation标记为PASS。
