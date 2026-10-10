# AI Task 创建 HTTP V1 增量合同

日期：2026-10-03；WBS：`AI-04-A05-P04`；依据冻结API-03 `AI_TASK_CREATE`、CR-AI-014、Schema0070。此文仅细化原冻结路径与DTO，不改变 `/api/v1` URL或控制标记。

## 请求

`POST /api/v1/projects/{project_id}/ai-tasks`

控制：`S,L,C,I,E,A`。要求可信Origin、有效Session、CSRF、`Idempotency-Key`，并由应用层在同一事务重核Project角色、Input Owner、Task Policy、当前ACTIVE PromptVersion及当前Egress Authorization。

请求JSON必须且只能包含：

- `task_type`：受控任务类型；
- `input_refs`：1～1000个 `{resource_type, resource_id, version_id}` 固定版本引用；
- `prompt_policy_ref`、`output_schema_ref`、`context_policy_ref`：受控版本化引用；
- `task_parameters`：最多16项的严格Task Policy标量参数，不接受嵌套对象/数组、null或浮点数；
- `egress_authorization_ref`：本轮逐次授权的规范非零UUID。

禁止API Key、endpoint、SDK类型、原始Prompt、Provider分支、完整正文或任意额外字段。重复JSON键、非标准常量、非UTF-8、查询参数和超限正文拒绝。

## 响应与错误

成功为 `202`：`data={ai_task_id,job_id}` 与公共 `trace_id`，并返回 `Cache-Control: no-store`、Task详情 `Location`。不返回Prompt正文、Task参数、Egress正文、Secret、Job payload或内部异常。

策略/Prompt不兼容映射冻结 `AI_PROMPT_VERSION_INVALID(422)`；缺少当前有效逐次授权映射 `AI_EGRESS_AUTHORIZATION_REQUIRED(403)`；输入不可解析或内部依赖失败不泄露细节，映射公共安全错误。Project越权隐藏为404，License、幂等冲突和通用验证沿用API-01。

## 装配边界

Router只能显式注入 `create_app(ai_task_create_router=...)`。默认应用和当前生产组合均保持404；本项不新增Provider调用或客户数据外发。Windows生产组合、非敏感Task Policy Bootstrap及Task读取/旧NULL执行拒绝由P05继续完成。
