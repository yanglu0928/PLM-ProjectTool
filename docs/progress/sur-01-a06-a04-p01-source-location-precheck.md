# SUR-01-A06-A04-P01：Survey 来源定位前置与 CR

日期：2026-10-06。结论：`SUR_01_A06_A04_P01_SOURCE_LOCATION_PRECHECK_PASS`。下一项：`SUR-01-A06-A04-P02` 来源定位内部 Owner 与最小 Adapter。

## 核查结果

- Survey 固定来源包含精确 question/source ordinal 与来源模块 row identity，但前端不能据此构造公共路由。
- Handover item 能由 Owner 解析为公共 analysis/item 标识和同 Project Evidence；Capability item 能解析公共 item 标识及其 Document/Evidence 引用，但 GLOBAL 原文仍需既有管理员权限；TEMPLATE 能证明固定 PROJECT/GLOBAL DocumentVersion；MANUAL 没有固定对象。
- 既有 Evidence Viewer 已能按点击重验 Scope、权限、固定 DocumentVersion、locator 与 fingerprint，因此定位增量只返回最小公共目标，不复制 Viewer 或正文。
- 历史来源“可追溯”与它“当前仍可用于新版本”不是同一事实；新响应必须分别表达，防止把已撤回/旧版来源误称为当前批准事实。

## 决策与边界

已按持续授权登记 `CR-SUR-006`，新增严格只读 location 子资源。来源解析由各模块 Adapter 承担，Survey 只负责编排精确固定来源、当前 Project 授权和公共投影。GLOBAL 目标不继承 Project 权限；MANUAL 无绑定时明确不可定位。

本项为文档/合同前置，无运行代码、Schema/Migration、依赖、配置、Secret、网络或外发变化。静态核对 Survey Schema/四读、三类来源证明 Adapter、Handover/Capability 引用表、Document 固定版本证明和 Evidence Viewer。P02/P03 未完成前不得宣称端点、浏览器定位或 Gate 3 通过。

