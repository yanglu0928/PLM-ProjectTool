# SOL-06-A16-P05：Review List HTTP 合同

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_HTTP_PASS`；本项只完成默认关闭的 HTTP Router，不表示 Windows 生产组合、正式 cursor key、Inbox UI 或 Gate/Pilot 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P05`|
|输入基线|冻结 REVIEW_LIST Path/Page、A16-P02 HTTP增量合同/AES-GCM、P04授权Service|
|前置任务|0166与内部Service已通过；Router可选注入，不依赖尚未实现的Windows Vault工厂|
|涉及模块|Review list Router、应用工厂可选插槽、HTTP合同测试|
|涉及实体|只映射P04只读Page；不直接访问数据库或创建业务事实|
|涉及 API|实现既有 `GET /api/v1/projects/{project_id}/reviews`，默认应用仍404|
|涉及权限|不在HTTP层复制权限；Session/Project/Owner由P04 Service执行，Host在边界检查|
|验收标准|严格query/UUID/游标绑定、最小白名单投影、错误映射、默认关闭、全量与wheel|
|风险|错误游标被映射503；query重复/未知被框架宽松接受；他人Assignment/意见泄露；默认应用误开放|

## 实施结果

- 新增可选 `create_review_list_router` 与 `create_app(review_list_router=...)` 插槽；未注入时冻结列表路径仍为404，P06完成正式密钥来源前不会自动开放。
- query只允许互不重复的 `view/page_size/cursor`；默认 `all/50`，页大小1～200，Project UUID必须canonical。游标解密绑定实际Session、Project、view和page_size；畸形或错范围统一400。
- 200响应严格为 `data.items/next_cursor/has_more` 和 `trace_id`；item仅含Review/Subject身份、policy/state/created、ETag、活动轮与当前actor Assignment最小字段。终态`active_round=null`，不返回其他评审人、意见、来源或内部锁。
- HTTP边界重新校验Page类型、页上限、Project绑定与DTO；续页位置可来自隐藏的最后消费候选，并由P02 AES-GCM编码。响应设置`Cache-Control:no-store`与`X-Content-Type-Options:nosniff`。
- Review Service错误稳定映射到401/404/403/422/400/503；Host不可信为403，非GET在已挂载Router上为405。解码器已有`ApplicationError`原样保留，不错误折叠为503。

## 验证证据

- P05合同：`4 passed, 19 subtests passed`，覆盖默认404/显式200、字段白名单、隐藏原始位置加密、默认/显式query、重复/未知参数、页大小/view、游标跨范围、canonical UUID、Host/Session、POST及全部服务错误映射。
- P02/P04及GET关联定向合计：`17 passed, 54 subtests passed`。
- 后端全量：`3777 passed, 3 skipped, 5918 subtests passed`；Router `compileall` 通过。
- Python 3.13开发wheel：1422项，Router与应用工厂均入包，SHA-256 `dfc7f450e4d3a9d9ac5453f8cf6909a93f977534d97e5ef7a4446b768a1af56b`；不是Pilot/Release包。

## 兼容、升级、回滚与未完成项

- 无Migration、冻结字段/角色、License、依赖或历史变化；需要数据库已升级0166。默认关闭保证旧部署行为不变；移除可选Router插槽可回滚，Review历史保留。
- 本项使用合成HTTP Service结果验证边界，未声称真实PG/Session/Subject已通过HTTP组合；P04只在内部Service层完成真实Session/Project/PG。
- Windows专用`review-list-cursor-v1` Vault来源、缺key启动失败关闭、显式只读/写组合及真实HTTP/PG留P06；前端/Edge、正式性能、Gate3/Pilot/发行仍未完成。

Next：`SOL-06-A16-P06` 增加Windows专用Review List cursor key工厂和显式读取/写模式组合，在Win11/PostgreSQL 18.6真实ASGI链验证权限、分页、游标、默认关闭与缺key失败关闭。
