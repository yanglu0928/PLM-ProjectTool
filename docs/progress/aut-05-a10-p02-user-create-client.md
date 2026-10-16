# AUT-05-A10-P02 管理员用户创建前端合同

2026-09-28 / 0.1.0.dev0 / PASS（前端创建客户端合同；页面与真实写链待后续）。

编码前检查：Phase2/Gate2已批准；输入冻结API-02 `AUTH_USER_CREATE`、CR-AUT-005、安全增量与P01私有CSRF桥接。DEC-414先登记；仅Auth前端DTO与响应解析，无实体/Schema/后端API/权限/依赖变更。回滚撤客户端/测试，无迁移。验收NFC用户名和UTF8密码预检、原Key单次提交、201安全八字段/初态/强ETag/Location、错误分流/不自动重试、前端全量test/typecheck/build。

实现：调用方传`username/password`及原幂等Key，客户端仅暂时拼请求JSON，不持久化/缓存密码、Key或canonical用户名。用户名NFC/去边空/Unicode控制字符/显示长度先查，Python casefold与唯一性由服务端最终判定；密码UTF8 1～1024 bytes且无NUL。201必须有效trace、user_id、NFC展示名一致、ENABLED/NONE/credential1、UTC时间、`"v1"`及强ETag/Location匹配；返回冻结八字段，绝不透出响应中额外密码、Hash、内部ID。确定401/403/404/409/400/422按状态码+已知错误码给固定提示；503/断线/非预期状态/畸形201标记可能已提交，不自动重试或使用新Key。

验证：新增30参数化场景，前端249/249测试、typecheck、Vite build通过。覆盖请求形状、Unicode/无效输入零请求、只读会话、确定拒绝、畸形响应/数据、传输故障与白名单。无本项真实浏览器/PG写、后端全量/性能；后续页面在不确定结果时必须清密码、锁用户名/原Key、同管理员重新输入原密码并明确确认后恢复。兼容现有0049无需升级；正式trust/HTTPS/CR008性能FAIL/Gate3/可用包仍待。
