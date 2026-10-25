# SUR-07-A01：调研定义创建私有客户端

日期：2026-10-25；状态：`FRONTEND_CLIENT_PASS / UI_PENDING`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A01`；单一问题是前端无法安全调用已冻结的调研定义创建 POST，不在本项增加页面、版本编辑或新 API。|
|输入基线|`PKG-PILOT-01-A04-P07` 已核对后端 Windows Router、交接来源资格和前端入口缺口；远端提交 `64040d65`。|
|合同|`POST /api/v1/projects/{project_id}/surveys`，精确 `{name}`，201 返回 survey/project/name/state/current_approved_version_ref/created_at/etag，ETag 与 Location；项目权限 PROJECT_MANAGER/IMPLEMENTATION_MEMBER。|
|实现边界|SessionClient 私有 CSRF/同源 POST、原幂等 Key 与体积上限；SurveyCreateClient 仅做输入/身份角色/冻结回执校验和可辨错误映射，结果未知保留原操作号由未来页面处理。|
|数据库/API/License|无 ORM、Migration、API 路由或 License 变化。|
|测试|定向客户端真 `SessionClient` 传输、权限/无效输入先拒绝、服务端错误/网络不确定、回执交叉绑定/ETag/Location；前端全量测试、typecheck/build。真实 Edge/PG 创建留给 UI 与包内独立 WBS。|
|风险/回滚|仅新增客户端与 Session 桥接，未接 UI 前无用户可见创建；可撤接线，不删除已有调研定义。不得把创建定义视为客户访谈确认。|

前置通过，允许本项编码；先跑定向测试后收口完整前端回归。

## 独立验收

- `SessionClient` 新增精确 `POST /api/v1/projects/{project_id}/surveys` 私有桥接，复用
  既有同源凭据、CSRF、8 KiB 正文上限、操作号、超时未知结果保护；不外露 CSRF。
- `SurveyCreateClient` 校验 canonical ProjectId、名称与当前项目角色，严格要求 201
  回执的字段集、项目/名称交叉绑定、初始 ACTIVE/null/`"v0"`、UTC 时间、
  ETag/Location、`no-store` 和 Trace 头体一致；识别冻结错误，传输未知时不自动重发。
- 定向 4 项通过；前端全量 189 文件/2016 项通过，typecheck 与生产构建退出 0。
  构建保留既有大 chunk 警告，无本轮新增依赖或安全例外。

结果只证明客户端合同，未接用户界面、未运行真实调研创建 HTTP/PG/Edge。
下一 WBS `SUR-07-A02` 在调研列表增加可理解的创建表单及原操作号恢复，再独立
执行固定包内创建验收；调研版本/实际面对面调研记录仍是后续任务。
