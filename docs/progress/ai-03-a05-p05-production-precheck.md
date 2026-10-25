# AI-03-A05-P05：Prompt 激活生产挂载前置核查

版本：0.1.0.dev0；日期：2026-10-02；状态：`PRECONDITION_BLOCKED`（仅生产挂载）；无程序变更。

依据：CR-AI-007 要求独立 Prompt 签名清单、包内公钥/固定摘要、真实人工审查、密钥备份和发行验收后方可开放写入/激活。P04 只证明临时合成材料下的可选 HTTP 链。

本机只读证据：`apps/backend/src/plm_assistant/modules/ai/trust/prompt_admission_release.json` 与 `prompt_admission_signed.json` 均不存在；当前入口代码只有 `create_app` 的可选 Router 注入点，没有 Windows 生产组合调用 `create_ai_prompt_version_router` 或 `create_ai_prompt_activation_router`。P04 合同和实际隔离 HTTP 均证实默认404。仓库没有正式审查签署/离线备份与目标账户发行验收记录。由此不能用测试私钥或临时清单冒充正式信任源，也不能开启生产路由。

Changed：记录阻塞和下一任务；不生成正式密钥/清单、不外发、不修改生产数据库。Migration/API/依赖：无。Tests：只读文件/入口搜索与 P04 已执行合同/PG18证据；未执行正式目标账户或发行包测试。兼容/回滚：现状保持关闭，无回滚操作。Known Issues：真实审查、独立密钥仪式/离线备份、包完整性、目标账户/Server2025/Debian、Gate3/UAT/可用包仍待。Next：转向不依赖该信任源的 `AI-03-A06` Prompt 退役内核；生产挂载前置保留开放。
