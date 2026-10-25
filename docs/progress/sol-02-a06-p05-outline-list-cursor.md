# SOL-02-A06-P05 SolutionOutline 列表独立签名游标

日期：2026-10-09。状态：游标编解码及 Windows 11 隔离 PostgreSQL keyset 串接通过；Windows 正式密钥来源、HTTP/组合未实现。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P05。
- 输入基线：冻结 `SOL_OUTLINE_LIST`、P04 内部 keyset、现有 PROJECT Reference 独立 HMAC 游标惯例。
- 前置任务：P04 真实项目成员/PG 分页 Owner 已通过。
- 模块/实体/API/权限：Solution API 层独立 cursor codec；不新增实体、公开 API 或权限。签名游标仅承载 Outline 根 ID，不代替每页 Session/License/项目授权复验。
- 验收标准：强制独立 32 字节密钥；签名载荷绑定 family、项目、当前 Session 摘要及 page size 查询指纹；篡改、其他会话/项目/尺寸、Reference 家族或密钥均拒绝。
- 风险：测试中固定字节仅为合成验证材料；正式 Windows 服务账户游标密钥的 Vault 来源/备份恢复仍待，不能直接开放列表 HTTP。

## 实施与验证

新增 `OutlineListCursorCodec`，采用规范 JSON + HMAC-SHA256 与 URL-safe Base64。解码时验证 token 形态、规范编码、签名、固定字段集合、家族/上下文及重新编码一致性，所有外部错误映射 `REQUEST_MALFORMED`。不复用 Reference 密钥或家族。

- 定向单元：3 passed / 12 subtests；覆盖往返、会话/项目/查询绑定、篡改、跨家族/异密钥及非法构造。
- Windows 11 隔离 PG18.6：P04 三根真实列表第一页 ID 经签名编码/解码后读取第二页，改变 page size 拒绝；临时数据库/进程由夹具清理。
- 后端全量回归：3379 passed / 3 skipped / 5072 subtests passed。
- Schema/Migration/依赖/冻结 API：无变更。删除独立 codec 即可回滚，历史保留。

下一项：`SOL-02-A06-P06` Windows 当前账户独立游标密钥来源与合成备份恢复；之后才做公开 LIST HTTP 与平台组合。正式服务账户/发行仍待。
