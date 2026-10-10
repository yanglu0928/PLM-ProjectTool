# AI-03-A04-P03-A01：签名清单只读准入

版本：0.1.0；日期：2026-10-02；状态：Win11 合成验签/隔离 PG18 内部链通过；正式信任锚、实际内容审查和公开装配未完成。

依据：冻结 PromptVersion 禁止内容规则、DEC-677、CR-AI-007。新增 `SignedPromptAdmission`：使用独立 Ed25519 公钥验签，并要求受信发行配置钉住清单文件 SHA-256；清单条目只含模板 UUID、受控 TaskType 和规范化正文/策略联合指纹，精确匹配后才向增版服务返回批准指纹。公钥或钉住摘要缺失、签名/格式/重复键/排序/作用域错误均失败关闭。

边界：本任务不生成、存储或交付正式私钥/公钥，不从 HTTP 请求接受公钥或期望摘要；测试仅使用进程内临时密钥和纯合成正文。签名证明清单来自密钥持有人且未篡改，不证明密钥持有人确实完成了语义审查，也不证明 Prompt 质量。正式审查记录、工作台签名仪式、发行钉住来源和目标账户/离线恢复留给 P03-A02；缺这些不能开放生产写路由。

Changed/Files：`apps/backend/src/plm_assistant/modules/ai/infrastructure/signed_prompt_admission.py`、单元测试、`validation/ai-03-a04-p03-a01-signed-admission/verify.py`、CR/决策/本进度/状态。Migration：无。API：无。兼容与回滚：无生产装配，停用适配器即可退回失败关闭；已有 PromptVersion 不物理删除。

Tests：签名、清单摘要、错公钥/篡改、重复 JSON key、错误形态/空或重复条目、过大/错误编码/签名形态、精确模板/TaskType/正文/策略指纹拒绝的定向单元 4 项通过；Win11 隔离 PG18 用临时签名清单实测未列正文拒绝、列入正文首次写入和重放通过；后端全量 2064 项通过、3 项按既有条件跳过；开发 wheel 构建通过，SHA-256 `5c13b723c6d896909610371243c4980548c0eb607ea19f41cc232bf4ac4d890e`。Golden Dataset 未运行：本项没有模型推理。

Known Issues：正式公钥及离线备份、清单审查签署与包级钉住未完成；Windows Server 2025/Debian 13、Gate 3/UAT/可用包未验。Next：`AI-03-A04-P03-A02` 工作台受控清单签署与发行信任锚来源。
