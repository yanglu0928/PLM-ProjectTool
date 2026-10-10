# AI-03-A05-P04：PromptVersion 可选激活 HTTP

版本：0.1.0.dev0；日期：2026-10-02；状态：Win11 合成合同及隔离 PG18 HTTP 链 PASS；生产挂载仍关闭。

输入：冻结 API-03 `AI_PROMPT_ACTIVATE_VERSION`、CR-AI-007/008、内部激活服务、Schema0061、DEC-688。Changed：可选 Router 处理受信 Origin、Session/CSRF、幂等键、强 If-Match、严格空 JSON 请求；结果与请求 Template/Version/预期锁版本二次核对后仅投影首次 ACTIVE/ETag，不泄露 Prompt。默认 App 不挂载，生产组合未变。

Files：`modules/ai/api/activate_prompt_version.py`、`entrypoints/api.py`、合同测试、Win11隔离PG18验证脚本、API运行时补充、DEC/状态/版本说明。Migration：无，复用0061。API：冻结路径与200/错误码不变；新增可选实现而非生产启用。

Verification：合同3项覆盖默认404、200/重放快照、请求畸形/权限/版本/许可/准入错误；Win11随机隔离PG18以临时 Ed25519 签名清单运行实际 HTTP→Session→服务→事务，默认/普通用户/未知版本404，200及重放、409、许可403，SQL仅一状态更新/Audit/结果/收据，随机库清理。后端全量2085运行、3项既有跳过；开发 wheel SHA-256 `af67942767f6b012cb807a493290e33bf419c3c5b0e6a94907f1a8f9a4ef0094`（临时输出未提交）。

兼容/升级/回滚：无新依赖/Schema/Breaking API；仅明确注入 Router 后可用，撤注入即恢复404，历史状态/结果/Audit/收据保留。风险：临时签名材料不代表真实审查；正式信任/目标账户/Server2025/Debian/安装/UAT/Gate3/可用程序包仍未验。Next：`AI-03-A05-P05` 正式生产挂载前置核查；未具备真实审查与发行信任时维持404并转向独立 AI-03 任务。
