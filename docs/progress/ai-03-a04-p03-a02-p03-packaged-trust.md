# AI-03-A04-P03-A02-P03：Prompt 准入发行信任只读装载

版本：0.1.0；日期：2026-10-02；状态：Win11 合成发行材料装载/失败关闭 PASS；正式发行材料与生产写入口未验。

依据：CR-AI-007、DEC-678～680。新增 `PackagedPromptAdmission`：启动时只从安装包内 `plm_assistant.modules.ai/trust/prompt_admission_release.json` 与 `prompt_admission_signed.json` 读入；无 HTTP、环境变量或请求级公钥/摘要覆盖。前者必须严格符合 `plm.prompt-admission-release.v1`、固定独立 `key_ref`、规范 base64 Ed25519 公钥、64 位小写 SHA-256 与正整数 generation；后者由既有 `SignedPromptAdmission` 验摘要/签名/条目结构，并与发行 generation 核对。任何缺失、重复 JSON 键、额外字段、错误摘要/公钥/签名/代际都在构造时失败关闭。装载成功后只委托精确指纹准入，不自动开放公开路由。

当前仓库故意没有正式 `trust/*.json` 文件。开发 wheel 经 ZIP 目录核查包含装载器、不包含这两份正式信任材料；默认装载报受信材料不可用。这不是可工作的正式发行配置，不能把合成注入源或本机可改文件冒充正式锚。未来发行须从已审查签署的清单制作受控公钥/摘要元数据，校验安装包完整性、目标账户读权限、离线升级和撤销/回滚行为；旧正式版本保留供追溯。

Tests：临时 Ed25519 签名清单与合成发行元数据的精确准入、改正文拒绝；错误摘要、公钥、代际、License key_ref、额外/重复字段、篡改及缺包材料失败关闭，共定向3项通过；后端全量2076项通过、3项既有跳过；开发 wheel 构建通过，SHA-256 `5af993942cd308d9e54f1d229da01d7d908e582caaf8156ee3699e2178002cd5`。真实审查、正式密钥/备份、Windows Server 2025/Debian 13、安装/升级与 Gate 3/UAT 未验。Golden Dataset 未运行：本项无模型推理。

Changed/Files：后端只读装载器、package-data 声明、单元测试、CR/决策/本进度/状态。Migration：无。API：无。兼容/回滚：未装配生产写路由，撤装载器或缺材料时恢复失败关闭；正式发行撤销需新受信包及清单，不能仅换环境变量。Known Issues：包完整性/正式材料/账户保护未验。Next：`AI-03-A04-P03-A02-P04` 工作台发行元数据生成与签名清单/公钥匹配验证；正式内容审查及密钥仪式仍独立待办。
