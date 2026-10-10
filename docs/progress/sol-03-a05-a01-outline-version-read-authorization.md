# SOL-03-A05-A01：OutlineVersion GET/LIST 项目读取授权

日期：2026-10-09。结果：`SOL_03_A05_A01_OUTLINE_VERSION_READ_AUTH_PASS`；仅项目授权矩阵，未开放版本读取 Owner/HTTP。

编码前检查：Phase 2 / 本 WBS；输入为 Gate2 冻结 `SOL_OUTLINE_VERSION_GET/LIST`、已有 Outline 读策略、`0156` 不可变版本表；前置 CREATE/Schema 已完成。单一问题是 Project 授权矩阵缺版本 GET/LIST 操作。仅涉及 Project Application 策略和矩阵测试，无实体/API/Schema/Migration/依赖变化。冻结合同要求 Project member 可读；风险是把策略存在误称公开版本 API 可用。

增加 `SOL_OUTLINE_VERSION_LIST/GET` 两项读策略，四类当前有效 Project member 均可用，沿用同项目成员校验和读取锁；不扩大 `SOL_OUTLINE_VERSION_CREATE` 的 PM/IM 写角色。授权矩阵定向 8 项/740 子例通过；后端全量 3456 项通过、3 跳过、5292 子例通过。无迁移，撤未接线策略可回滚；现有数据和冻结 `/api/v1` 均不变。下一项 A05-A02 实现受权 OutlineVersion 固定历史读取 Owner，并核验有序 Section/Requirement/Reference 关联；HTTP/Win11/UI/浏览器另项。Gate3 仍 BLOCKED。

TraceLink：Gate2 API-04 → 0156/CREATE → 本读策略 → A05-A02 Owner → GET/LIST HTTP/Windows/UI。
