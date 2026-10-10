# AI-02-A08-P03：模型安全状态可选 HTTP

日期：2026-10-02；状态：Windows11 隔离 PostgreSQL18.6 可选 HTTP 链 PASS。依据 CR-AI-004/005、DEC-672、冻结 `AI_MODEL_SET_STATE`。

Changed：新增可选 POST `/api/v1/admin/ai/models/{model_id}:set-state`，正文严格仅 `{"state":"SUSPENDED"}` 或 `{"state":"RETIRED"}`；Origin/CSRF、Session、强 If-Match、幂等键及有界 JSON 准入。调用 P02 内部命令并返回安全状态/ETag，不公开 Audit/Secret/厂商异常。AVAILABLE 明确拒绝。默认/当前 Windows 生产组合不挂路由。

Tests：合同3项；`validation/ai-02-a08-p03-model-state-http/verify.py` 在隔离 PG18 验证默认404、AVAILABLE422、非法前态409、首次200/同 Key重放、强版本、普通用户404、License403、模型/结果/Audit唯一。后端全量2052运行/3跳过；临时 PG 停止。开发 wheel SHA-256 `e61e081c1dd205ff3e7988c1ef064b743ebff6e54da76c262b52262f70d66f81`。

Migration：无，复用0058。API：冻结 `:set-state` 的受限可选实现，无 Breaking Change。兼容与回滚：撤注入可回退，历史状态/结果/Audit 保留。Known Issues：P04 Windows 装配、真实质量 Owner/AVAILABLE、正式目标账户与三平台、Gate3/UAT/可用包未验。Next：`AI-02-A08-P04` 显式 Windows 写组合。
