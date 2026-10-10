# AI-03-A04-P03-A02-P04：Prompt 发行元数据准备

版本：0.1.0；日期：2026-10-02；状态：Win11 合成公钥/签名清单互通 PASS；正式发行材料未生成。

依据：CR-AI-007、DEC-678～681。新增仅开发者工作台使用的 `tools/developer-workbench/prompt_admission_release.py`。命令 `python tools/developer-workbench/prompt_admission_release.py prepare ABS_PUBLIC_JSON ABS_SIGNED_JSON ABS_OUTPUT_RELEASE_JSON`；输入仪式公钥元数据及已签无正文清单，先以该公钥验清单 Ed25519 签名/结构，再计算清单 SHA-256 和 generation，独占写仓库外 `plm.prompt-admission-release.v1` 元数据。不能自报期望摘要、覆盖旧输出或从清单内取“可信公钥”。输出与 P03 装载器合成互通；仍需人工检查真实审查记录、离线备份与发行包完整性，不能凭工具签发自动发布。

Changed/Files：工作台生成器、定向测试、CR/决策/本进度/状态。Migration：无。API：无。兼容与升级：不更改已发布运行时；正式发行时须将经审查的公钥/摘要元数据及配套签名清单一起打入受控包，升级代际和回滚须复验配对与历史留存。测试仅用临时 Ed25519 密钥及纯合成正文；未生成正式私钥、公钥或清单。

Tests：定向3项通过，覆盖生成→P03 包装载精确准入、错公钥/篡改/重复 JSON 键/非法编码/超大清单拒绝、CLI 独占输出且无正文/私钥；与装载器合计定向6项通过。后端全量2079项通过、3项既有跳过。开发 wheel 本项未重建（仅新增工作台工具与测试，后端包代码未变；P03 wheel 构建已通过）。Golden Dataset 未运行：本项无模型推理。

Known Issues：正式人工内容审查、操作员密钥/离线备份、包完整性/目标账户和离线安装升级未验；Windows Server 2025/Debian 13、Gate 3/UAT/可用包未验。Next：`AI-03-A04-P03-A03` PromptVersion 公开写合同与明确失败关闭装配前置；正式准入材料未到位时不开放生产路由。
