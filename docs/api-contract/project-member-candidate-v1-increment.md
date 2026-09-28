# CR-PRJ-006：项目成员精确用户候选增量合同

2026-09-28 / `PRJ-05-A07-P03-A01`。Gate2冻结 API-02 和提交`64cdf09`保持不变。本页只增加非破坏性可选读取端点，不修改`AUTH_USER_LIST`管理员目录或原`PROJECT_MEMBER_CREATE`写入合同。

|项目|合同|
|---|---|
|方法与路径|`POST /api/v1/projects/{project_id}/member-candidates:resolve`；只读业务语义但持久计数限流，不提交成员|
|权限|可信Origin/Host、当前有效Session和私有CSRF、License、当前ACTIVE项目的ProjectManager；复用成员创建实时权限检查，DeploymentAdmin身份本身不授权|
|输入|`Content-Type: application/json`、恰好`{"username":"exact_name"}`，不接受URL查询参数/额外或重复JSON字段；使用与登录一致的NFC/大小写折叠规范，显示长度1～255、规范长度1～128、拒控制字符；畸形400，值无效422|
|成功|`200 {"data":{"candidate":{"user_id":"uuid","display_name":"name"}|null},"trace_id":"uuid"}`；仅精确匹配且当前ENABLED、具活动凭据、没有任何非REMOVED成员时返回候选|
|未命中|目标不存在、停用或已经在任一项目分配均为同一`200 candidate:null`，不暴露其他项目归属；已REMOVED的历史不阻止候选|
|失败|未知/过期Session401、可信Host失败/许可拒绝403、非项目负责人/跨项目404、已归档409、持久限流429、未知来源503；错误只用平台固定Envelope|
|限流|复用PostgreSQL摘要计数桶，无原用户名存储；负责人+项目30次/5分钟，负责人+项目+规范用户名10次/5分钟。命中/未命中均计数，拒绝保留已消耗的负责人容量；无业务幂等Key，用户应在429后等待窗口而非盲重试|
|缓存与副作用|`Cache-Control:no-store`、`X-Content-Type-Options:nosniff`；无成员/用户/Audit写入，限流桶写入；候选只是页面提示，原POST仍独立校验User/成员状态|

默认应用不挂载此端点，`create_app`仅显式注入时开放；Windows生产组合接线留下一独立WBS。原先考虑GET查询串，因目标用户名可能进入URL历史/代理日志且跨站可耗额度，实施前收敛为带Origin/CSRF的POST。无Schema/Migration/依赖或升级步骤，兼容DB head0049；回滚撤可选路由/服务和本增量合同。合成HTTP/Unit与一次性PostgreSQL18全迁移实际Session/User/Project/Member/限流已验；正式目标账户/Server2025/Debian/HTTPS与浏览器流程未验。
