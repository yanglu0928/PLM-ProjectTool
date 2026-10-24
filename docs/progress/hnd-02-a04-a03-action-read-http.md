# HND-02-A04-A03：Action LIST/GET cursor 与可选 HTTP

日期：2026-10-05。结论：`HND_02_A04_A03_ACTION_READ_HTTP_PASS`。下一项：`HND-02-A04-A04` Windows组合与真实HTTP/PG验证。

## 实施结果

- 新增专用HMAC-SHA256 Action列表cursor，绑定资源族、Session摘要、Project、page size及`updated_at/action_item_id`完整位置；严格规范化编码并拒绝篡改、换key、跨会话/项目/页长复用。
- 新增可选LIST/GET Router：可信Host、当前Cookie Session、唯一查询参数、页长1～200、无查询详情、`Cache-Control: no-store`；详情返回强ETag。
- LIST只投影安全摘要；GET防御性校验来源形状、owned refs上限/顺序/UUID、当前事件与Root状态一致，不返回内部TraceId、物理路径、Evidence正文或Trace端点。
- `create_app`仅新增可选Router注入点；默认应用保持404，Windows生产组合未接入。

## 验证

- cursor与HTTP合同6项通过：两页、详情/ETag、安全字段、默认404、cursor上下文/篡改、未知/重复参数、错误映射及资源隐藏。
- 后端全量2657项通过/3跳过；开发wheel构建及解包导入通过，SHA-256 `485980beef8b8ad65ef465bcc010f1e60a47f7ba1febff94ef185495f360d76c`。
- 本项无真实HTTP/PostgreSQL组合、正式cursor密钥、浏览器或生产监听验证；A04独立完成。

## 兼容与回滚

无Migration、冻结API破坏、依赖、配置、网络或外发变化。移除可选Router注入与cursor即可恢复默认404，内部A02读取Owner不受影响。Gate 3继续BLOCKED。
