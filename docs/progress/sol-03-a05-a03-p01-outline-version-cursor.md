# SOL-03-A05-A03-P01：OutlineVersion 历史列表专用签名游标

日期：2026-10-09。结果：`SOL_03_A05_A03_P01_OUTLINE_VERSION_CURSOR_PASS`；仅游标合同，GET/LIST HTTP 与正式游标密钥来源未开放。

编码前检查：Phase 2 / 本 WBS；输入为冻结 `SOL_OUTLINE_VERSION_LIST`、A05-A02-P02 版本号倒序 Owner 与现有专用 HMAC 列表游标模式；前置满足。仅 Solution API 游标与测试，无实体/Schema/Migration/HTTP 改动。项目成员权限仍由后续 Owner 校验。验收为独立 32 字节签名密钥、Session/Project/Outline/页大小/版本位置绑定，篡改或跨范围复用一律拒绝。风险为复用其他游标 key 或泄露 Session；本项使用独立 family 与 Session SHA-256 摘要，不含令牌原值。

新增 `OutlineVersionListCursorCodec`，将 `before_version_no≥2`、项目、目录、页大小和当前 Session 摘要放入规范 HMAC-SHA256 游标；解码验证规范 Base64、MAC、字段全集、family 与所有绑定信息，并重编码核对规范表示。无数据库 Migration、冻结路径/角色/依赖变化；可撤未接线游标，历史版本不变。定向 2 项/11 子例通过；首轮测试误读 `ApplicationError.code` 属性，修正为 `spec.code` 后重跑通过。后端全量 3463 通过、3 跳过、5314 子例。未进行独立生产密钥 Vault/恢复或 HTTP/PG 分页验收；Gate3/发行仍 BLOCKED。

下一项 `SOL-03-A05-A03-P02` 可选版本 GET/LIST HTTP，默认仍 404；Windows 独立游标签名密钥来源另项。TraceLink：Gate2 API-04 → A05-A02 Owner → 本签名游标 → HTTP/Windows/UI。
