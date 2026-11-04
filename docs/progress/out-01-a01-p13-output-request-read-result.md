# OUT-01-A01-P13：OutputRequest 固定版本只读详情结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-010
- 代码提交：9442797bd3d94704f94214adef318bc09fbc08af；测试与安全投影补强：4a0b34d2f0098a348f532fc8d2791408b9af0041
- Hosted run：[41785576480](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41785576480)

## Changed / Files

- 新增 OutputRequest 固定版本只读 Application Service 与 SQLAlchemy repository。
- 新增可注入的 GET `/api/v1/projects/{project_id}/output-requests/{output_request_id}`；默认路由未挂载。
- 响应只含请求ID、ProjectID、输出类型、固定模板/来源/策略/插件操作引用、Context fingerprint、状态、Job/Execution refs、generation、时间和 ETag。
- 查询对请求行与 ContextSnapshot 均限定 ProjectId；只选取必要列，不读取 Context 正文、幂等键或存储路径。
- Project active-member read authorization、Session及License检查在同一Application事务中执行；未授权Project、跨项目与不存在请求统一404。
- GET不要求CSRF或Idempotency-Key，异常只映射安全错误码。
- Files：`application/read_request.py`、`infrastructure/read_request_repository.py`、`api/read_request.py`、三项HTTP/service/repository测试。
- Migration：无。
- API Contract：无变化；实现API-03已有 OUTPUT_REQUEST_GET。默认生产组合仍未挂载。

## Tests / Result

Hosted run 41785576480 的14/14 jobs通过：后端3,988项测试及wheel、前端测试/typecheck/build、PG18/pgvector runtime、非发行父包、A17 Edge/HTTPS/PostgreSQL、A34替换/恢复演练、A35与A50。

定向新增测试覆盖安全详情投影、Session失败、跨项目/非成员404、查询参数拒绝、异常归一、Project授权及SQL PostgreSQL dialect的双重范围过滤和敏感列排除。父包PG18生命周期 smoke通过，但本WBS没有在真实PG18数据库中用正向OutputRequest数据行直接执行该repository；所以验收为PASS_SCOPE_LIMITED，不能据此宣称数据库端正向集成通过。

## Known Issues / Limits

- 详情router仍为opt-in，未挂载到默认应用或Windows生产组合。
- 没有产品API启动、真实信任锚、Windows 11实机、客户数据、插件执行或文件生成证据。
- OutputRequest repository的真实PG18数据集成测试待后续Output读路径组合/集成验证。
- Pilot、Gate 3及正式Release状态保持NOT_READY。

## Next

OUT-01-A01-P14：对冻结 OUTPUT_REQUEST_LIST 进行编码前核查，确认角色矩阵、稳定分页/签名cursor及可复用授权/密钥来源后实施。
