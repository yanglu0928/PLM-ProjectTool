# AI-03-A04-P03-A02-P01：工作台离线签署工具

版本：0.1.0；日期：2026-10-02；状态：Win11 合成签署/验签互通 PASS；正式密钥、人工内容审查与发行装配未验。

依据：冻结 PromptVersion 禁止内容规则、CR-AI-007、DEC-678。新增仅在开发者工作台运行的 `tools/developer-workbench/prompt_admission_sign.py`。输入完整候选正文和策略引用，由正式 Domain 计算指纹，不接受调用方自报指纹；排序/唯一性/元数据形态沿用运行时清单验证器。交互式终端展示源文件 SHA-256，要求审查人员输入完整摘要，并从隐藏输入读取独立 Ed25519 加密私钥口令。成功后只在仓库外独占创建无正文签名清单，打印其 SHA-256；错误不输出正文、口令或私钥。

候选文件是 UTF-8 JSON，根对象仅有 `drafts` 数组（1～256）。每项必含 `prompt_template_id`、`task_type`、`system_template`、`user_template`、`output_schema_ref`、`schema_version`、`rag_policy_ref`、`provider_policy_ref`。候选和输出必须放在仓库外的绝对路径，私钥为加密 PKCS#8 PEM。命令：`python tools/developer-workbench/prompt_admission_sign.py sign ABS_CANDIDATE_JSON ABS_PRIVATE_PEM ABS_OUTPUT_JSON REVIEWER_REF GENERATION`；运行前必须以人工检查候选正文中的秘密、客户资料固定副本、Golden 答案及绕过 Evidence/Review 的指令，且单独保存审查记录。摘要输入仅证明操作者选择签该文件，不证明完成语义审查。

本项发现三个引用字段只校验 Ref 字符集而不拒明显密钥形态；已按 CR-AI-007 加同正文的明显密钥形态先行拒绝。此检查不能识别任意秘密，正式人工审查不能省略。无运行时安装、数据库迁移或 API 改动；工具不进入客户 wheel。旧合法引用保持兼容；回滚工作台工具不影响生产，撤回 Domain 增强会重开已发现风险，不建议。

Tests：临时加密 Ed25519 密钥、纯合成候选的签署→现有运行时验签→精确 Draft 准入通过；错误摘要/口令、重复/无效候选、密钥样式引用、重复清单条目、交互式 CLI 不覆盖及错误确认无产物共 6 项定向通过；签名清单不包含测试正文；后端全量 2070 项通过、3 项既有跳过；开发 wheel 构建通过，SHA-256 `d91f0f27064056d04593546163cb213bc26d66045e66bde6bc49420047290601`。Golden Dataset 未运行：本项无模型推理。正式密钥、真实审查、正式目标账户/发行钉住、Windows Server 2025/Debian 13、Gate 3/UAT/可用包未验。

Changed/Files：工作台签署工具、合成单测、PromptVersion Domain 输入规则、CR/决策/本进度/状态。Migration：无。API：无。Known Issues：正式独立私钥/公钥创建及离线备份、人工审查证据、受信发行公钥/清单摘要装配均未完成。Next：`AI-03-A04-P03-A02-P02` 工作台独立密钥仪式及清单发行前核验（不能把本次临时密钥当生产身份）。
