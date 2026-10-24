# AUT-05-A12-P02 管理员User启停安全响应客户端

2026-09-28 / 0.1.0.dev0 / PASS（前端客户端合同）。

编码前检查：Phase2/Gate2已通过；输入冻结`AUTH_USER_ENABLE/DISABLE`、CR-AUT-006不可变首次结果、P01私有POST传输。DEC-420先登记；仅Auth前端客户端与测试，不修改实体/Schema/Migration/后端API/权限/依赖。验收目标/动作/强版本+1/响应ETag绑定、安全8字段、时间顺序、确定错误与结果未知分离、无证明零请求、frontend test/typecheck/build。风险为首次响应是历史快照而非当前状态，且self-disable重放不等于当前Session撤销；页面必须另取当前授权或提醒人工核对，不凭历史结果推断当前状态。回滚撤新客户端/测试，无迁移。

实现：`AdminUserStateClient.change`仅接受合法UserID、启停动作、强`"vN"`及原幂等Key；返回冻结的`user_id/username_display/account_state/deployment_role/credential_version/created_at/updated_at/etag`，剔除私有撤销计数、凭据、canonical与服务端错误细节。对明确的401/403/404/409、请求拒绝作确定分类；503、网络异常、畸形成功或无法匹配状态码均为结果未知，保留原目标/版本/Key待恢复。P01传输拒绝不可安全递增的最大JS整数版本。

验证：新增21场景，前端292/292、typecheck和Vite build通过。首轮测试因新客户端UUID正则少一段、TypeScript安全返回字段未收窄而失败；修正并重跑全套通过。未在本项执行实际HTTP/PG或浏览器端到端；UI、正式trust/TLS/性能/Gate3/可用包仍待。兼容0049，无Migration/API/权限/依赖变更。
