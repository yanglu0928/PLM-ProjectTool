# SOL-01-A04-P08-P03-P01：人工确认写时预览指纹栅栏

日期：2026-10-09；结果：`GLOBAL_REFERENCE_CONFIRMATION_FINGERPRINT_FENCE_PASS`，内部命令/隔离 PG 验证；Preview/Confirm HTTP 尚未开放。

编码前检查：Phase 2；输入冻结 API-04、CR-SOL-006/007/009 与 P08-P02 合同；前置内部确认/撤回/真实来源 Proof 通过；仅改 Solution 确认命令及其验证，不改 Schema、旧 API 或权限。验收为调用方提供预期指纹时与写时服务器现时来源常量时间比对，不一致在记录/Audit/收据前拒绝，旧内部调用保持兼容；风险是 HTTP 尚未强制提供该值，需 P03 后续子项完成。

`ConfirmReferenceDeidentification` 增可选 32 字节 `expected_source_fingerprint`。服务端仍由当前 Document/Evidence 物理证明、分类和适用性重算来源指纹；给出预期值时不一致返回内部 `SOURCE_SNAPSHOT_CHANGED`，不以客户端指纹代替来源证明。后续公开 Confirm HTTP 必须把该字段列为必填并映射 `409`；无 Preview/页面前不产生真实人工确认。

验证：定向单元 6 通过/5 子例，含匹配、漂移、畸形长度与零额外写；既有确认 Owner PG Schema/Audit/收据回归、真实 Auth/Document/Evidence/私有文件 PG 正确与错误预期指纹回归均退出 0；后端全量 `3323 passed, 3 skipped, 4906 subtests passed`。无迁移、依赖或部署动作。回滚可移除可选栅栏且历史记录不变，但公开 HTTP 启用后不得无保护回退。正式 License/服务账户、真实用户操作、Server 2025、Gate 3/发行仍未通过；Debian 13 依指令跳过。

TraceLink：CR-SOL-009/P08-P02 → P08-P03-P01 命令/单元/PG/全量 → P08-P03-P02 Preview Owner → 后续 HTTP/Windows/UI。
