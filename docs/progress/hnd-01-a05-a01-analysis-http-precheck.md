# HND-01-A05-A01：Handover Analysis HTTP 与读取Owner前置

日期：2026-10-05。结论：`HND_01_A05_A01_ANALYSIS_HTTP_PRECHECK_PASS`。下一项：`HND-01-A05-A02` Analysis/Version/Item读取Owner与有界分页。

## 冻结范围与现状

API-04冻结Handover Analysis共11个Operation：Analysis LIST/CREATE/GET/PATCH/ARCHIVE，Version LIST/CREATE/GET/ITEM_LIST/VALIDATE/SUBMIT_REVIEW。当前内部已有真实CREATE、VERSION_CREATE、VERSION_VALIDATE、HND-02 Review Subject/终态消费；公开Analysis/Version/Item Router数为0，读取Owner、Analysis PATCH/ARCHIVE Owner和业务专用原子SUBMIT_REVIEW Service也为0。

P04完成的通用Review create/start两步端点不取代`HND_VERSION_SUBMIT_REVIEW`。冻结API-04要求该业务端点先完成来源、Evidence、Action覆盖、指纹和状态校验，再在同一业务编排中创建并启动固定Version的ReviewRound。前端不得用两次通用HTTP请求模拟该原子命令。

## 实施分解

|WBS|唯一问题|验收边界|
|---|---|---|
|`HND-01-A05-A02`|Analysis/Version/Item只读Owner与内部完整位置|当前四类Project成员、固定Version投影、有界稳定分页、零业务写|
|`HND-01-A05-A03`|Analysis metadata PATCH/ARCHIVE Owner|ACTIVE、强ETag、角色、Review写栅栏、Audit/幂等和终态保护|
|`HND-01-A05-A04`|CREATE/VERSION_CREATE/VALIDATE写HTTP|严格DTO、最小投影、默认关闭，不重写既有Owner|
|`HND-01-A05-A05`|HND_VERSION_SUBMIT_REVIEW原子业务编排|Owner事实重验与Review create/start/收据/Audit同事务，不暴露中间DRAFT Review|
|`HND-01-A05-A06`|五读Router与三类cursor|LIST/GET/Version/Item安全白名单，不复制文档正文/Evidence定位或AI输入|
|`HND-01-A05-A07`|Windows读/写组合与真实HTTP/PG|只读模式五GET，写模式全11 Operation，正式cursor密钥缺失失败关闭|

## 约束与验证

- Analysis identity元数据只有`analysis_purpose`可补充为PATCH输入；`source_set_ref`、当前正式指针、状态和版本内容不由PATCH直接修改。Archive不删历史，IN_REVIEW不允许静默绕过Review。
- 读取只返回身份/状态/固定引用/短文本和ETag；Evidence Viewer、Document content和AI Task仍需各自当前授权。
- 本项为静态交叉核查与分解，无代码、Schema、配置、Secret、网络或数据外发；不将缺失Operation标PASS。
