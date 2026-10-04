# AI-03-A04-P03-A02-P02-P01：Prompt 独立密钥仪式工具

版本：0.1.0；日期：2026-10-02；状态：Win11 临时密钥工具验证 PASS，正式仪式待操作员。

依据：CR-AI-007、DEC-678/679。新增 `tools/developer-workbench/prompt_admission_key_ceremony.py`，仅开发者工作台使用、不会进入客户 wheel。`create` 在被 Git 忽略的 `tools/developer-workbench/private/` 独占创建新的独立 Ed25519 加密 PKCS#8 私钥和公钥元数据；`verify [absolute-private-copy]` 对原件或离线副本与公钥执行挑战签验。公钥格式/引用 `plm.prompt-admission-public-key.v1` / `plm-prompt-admission-release-v1`，与 License 公钥身份分开；错误或重复文件均失败关闭，不覆盖旧密钥。口令隐藏输入，字节数组在处理后清零。

正式操作前置：由开发者工作台实际操作员在交互式终端运行 `python tools/developer-workbench/prompt_admission_key_ceremony.py create`，单独备份加密私钥与口令、保管备份位置并用 `verify ABS_OFFLINE_PRIVATE_COPY` 复验；不得把私钥/口令写入 Git、客户包或服务器。本任务没有运行正式 `create`，没有正式密钥、备份或人工保管证据。测试只在操作系统临时目录中生成和删除纯合成密钥。

Tests：定向3项通过，覆盖创建/原件/离线副本、拒绝覆盖、短/错误口令、伪造元数据及 License 公钥身份混用；工作台签署定向6项回归通过。后端全量2073项通过、3项既有跳过；开发 wheel 构建通过，SHA-256 `21f28eeab2d0b861f58fdb178876753038a4f660154c4b5078f8a9276c41cf81`。正式目标账户、Windows Server 2025/Debian 13、安装/升级、Gate 3/UAT/可用包未验。

Changed/Files：工作台仪式工具、合成单测、CR/决策/进度/状态。Migration：无。API：无。兼容与回滚：未修改生产装配，可撤工具而不影响既有运行；已签清单的换钥须重新签发并随发行钉住新公钥/摘要，不能靠覆盖原密钥。Known Issues：正式操作员/口令和独立离线备份未完成；仅有工具不能标生产信任。Next：`AI-03-A04-P03-A02-P03` 发行公钥和清单摘要的受信只读装载/缺失关闭，可先用纯合成材料验证；正式仪式另行收口。
