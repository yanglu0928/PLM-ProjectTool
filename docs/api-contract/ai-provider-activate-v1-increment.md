# AI_PROVIDER_ACTIVATE 实现增量（冻结合同不变）

版本：V1；日期：2026-10-02；WBS：`AI-01-A05-P05-A03-P03`。

`POST /api/v1/admin/ai/providers/{provider_id}:activate` 仅在显式注入 Router 时开放；默认应用 404，当前 Windows 平台组合尚未挂载。请求需要可信 Origin/Host、当前 Cookie Session、`X-CSRF-Token`、强 `If-Match: "v<lock_version>"` 和合法 `Idempotency-Key`；不接受请求体或 query。内部再次校验 DeploymentAdmin、License、当前 Provider/Secret/受控策略、最新终态成功探针和版本。激活不调用厂商，也不外发客户数据。

成功固定 `200`：`data.provider_id`、`data.state=ACTIVE`、`data.etag`、`trace_id`；头含同值强 `ETag`、`X-Trace-Id`、`Cache-Control: no-store`。同 actor/Key/请求重放原首次激活快照，即使当前 Provider 后来暂停，仍返回原 `ACTIVE`/ETag，不能据此判断当前运行状态；需要当前状态应另取 Provider GET。异载荷 409。无权/不存在 404、许可或 CSRF 403、缺版本 428、版本/状态/无当前证明/幂等冲突 409、格式 400、输入 422、Provider/Secret/策略暂不可用 503。不得回显 Secret、Endpoint 或内部探针详情。

本增量不修改 Gate 2 冻结路径、角色和 `200 ACTIVE` 合同；正式组合、生产信任/Worker、真实外发和三平台发行另行验证。
