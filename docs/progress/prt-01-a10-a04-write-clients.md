# PRT-01-A10-A04 Prototype 受控写传输与未知结果恢复

日期：2026-10-08
状态：`PRT_01_A10_A04_WRITE_CLIENTS_PASS`

```text
前置任务：PRT-01-A10-A03 PASS
涉及模块：SessionClient、Prototype frontend write client
涉及实体：Package、Prototype、ScopeDecision、TemplateVersion、PrototypeVersion、Review、RequirementPrototypeLink
涉及API：冻结17项Prototype写操作；不增加或修改服务端路径
涉及权限：浏览器只提供Session/CSRF；服务端仍逐请求重证License、角色、资源和当前状态
验收标准：路径白名单、请求字段严格、强ETag、幂等原样重放、PATCH未知结果GET对账、成功响应失败关闭
风险：隐式重试重复写、PATCH伪幂等、Key/ETag漂移、只读投影回写、错误消息或私有字段泄露
```

## 实现结果

- `SessionClient.writePrototype`以运行时白名单构造冻结17项路径，调用方不能提交自由URL。所有请求固定
  same-origin、no-store、redirect:error、CSRF和JSON边界；资源ID、Body/Empty Body、ETag、Key组合不符合
  对应Operation时在网络前拒绝。
- Package/Prototype名称PATCH是冻结合同中的非幂等写，只携带强`If-Match`，绝不伪造或附加幂等键；响应
  丢失时返回`uncertain=true`，页面必须先GET对账，客户端不自动重发。
- 其余15项命令按合同携带原始Idempotency-Key，需并发控制的操作同时携带原始强ETag。网络/超时未知时
  不自动重试；调用方保留相同输入、Key和ETag可显式恢复，测试证明两次字节级Body/Header一致。
- 五族写客户端严格验证结构化输入、排序/去重、Coverage完整分区、固定Review Policy、安全JSON合同、
  DocumentVersion写引用仅含`artifact_kind+target_id`，拒绝只读`document_id`回写。
- 成功响应严格核对Envelope、父级ID、状态组合、Header/body ETag、Location、内容指纹、Version/Review/Link
  身份。公开错误只在状态码匹配时映射；私有消息、错配码、HTML或畸形成功统一失败关闭。

## 验证、兼容与回滚

- Session/Prototype Read/Write定向208项通过，其中A04新增12项覆盖17条路径、Header/Body策略、显式恢复、
  PATCH未知结果、输入拒绝、错误映射和畸形响应。
- Windows 11前端全量95文件/1575项、Vue/TypeScript typecheck、Vite 195 modules生产构建通过；既有
  主chunk大于500kB警告仍为非阻断发行优化项。
- 无Schema/Migration、服务端API、依赖、角色、Secret、客户数据或外发变化。删除新增写客户端和Session
  白名单方法即可回滚；后端与历史不变。A05将实现结构化页面及人工维护提示，A06导航/撤权，A07真实Edge。
  当前不声称页面、Windows Server 2025、Gate 3、UAT或发行通过，Debian 13按用户指令跳过。
