# OUT-01-A01-P20：OutputRequest GET显式Windows只读组合编码前检查

- 日期：2026-11-04
- 结果：PASS_WITH_LIMITATION，可开始单项实施
- Change Request：CR-OUT-016
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P20

## 单一目标

将冻结的 `GET /api/v1/projects/{project_id}/output-requests/{output_request_id}` 详情路由接入Windows显式只读组合；默认、登录及不具备Secret read信任的应用保持不挂载。

## 编码前检查

- P13已提供固定OutputRequest read Service、项目内Read Repository与opt-in HTTP adapter；详情只包含固定refs、Context fingerprint、状态与JobRef，不返回Context payload、路径、Secret或Artifact。
- Read Service依赖当前Session读取、License guard、授权Project读取与Output只读Repository；现有 `SqlAlchemyProjectReadAccess`、`SqlAlchemyProjectReadRepository` 与 `SqlAlchemyOutputRequestReadRepository` 可复用。
- API-03角色为创建者/受权项目角色；只读授权必须继续由现有Project成员读取Owner执行，跨项目/不存在统一返回404。
- 需新增Windows Read组合factory，并且只在 `include_secret_read` 分支挂载；不接触Create、List、Cancel、Worker或输出文件，不改API/Schema/Migration。
- 生产License/Session信任仍依赖现有正式装配；hosted验收只证明合成session与PG行为，不代表真实信任或Win11实机。

## 验收计划

1. 测试默认App无详情路由、显式Read组合挂载GET；
2. GitHub hosted PG18.6合成项目/请求/身份验收授权读取、跨项目404与最小投影；
3. 后端全量/wheel、前端与Windows父包/A17/A34/A35/A50全链云端回归；只在runner D盘临时目录执行；
4. 仅在所有证据通过后标记P20结果。正式信任、Win11实测及Gate/Pilot/Release独立保留。
