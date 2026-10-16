# AI-03-A07-P04：Prompt 只读 Windows 显式平台装配

日期：2026-10-02；版本：0.1.0.dev0；依据冻结 `AI_PROMPT_LIST/GET`、DEC-695/696。

Changed：Windows 当前账户 Vault 新增独立 `ai-prompt-list-cursor-v1` 32字节游标签名密钥只读来源，缺失/损坏时显式平台组合启动失败关闭；只在 `--platform` 与 `--platform-write` 装配 Prompt LIST/GET，默认登录模式仍404。目标账户正式密钥须按现有受控供给与离线备份流程准备，不把本机测试密钥当正式来源。无需 Prompt 内容签名清单即可读取最小元数据；增版/激活仍保持关闭。

Files：Windows密钥来源、`production_login.py`、Vault/组合合同测试、隔离PG18验证及既有合成组合脚本的测试密钥注入。Migration/依赖/冻结API：无变化。升级/回滚：显式平台服务启动前先供给独立密钥并验证备份恢复；回滚撤销只读Router装配，历史Prompt与其他游标签名密钥不动。密钥缺失仅使显式平台组合拒绝启动，不改变默认登录模式。

Tests：Win11 临时Vault密钥丢失/加密备份恢复，专属引用/坏密钥失败关闭2项 PASS；合同涵盖两平台模式缺密钥启动失败且无敏感错误泄露；隔离PG18登录404、读/写组合两页与详情ETag、普通用户404、License403、无正文、缺钥失败关闭 PASS。回归 Model创建/状态组合与Prompt退役组合：首轮退役在只读组合因详情宽泛路径由404变405，改为UUID路径匹配后恢复404并全部重跑 PASS；后端全量2100运行/3跳过 PASS。开发wheel SHA-256 `f712ba6dcd7e01e0f7629ec10a8ad4c8f76aa9ef63ac75a21a52925d13a78c70`，非交付包。

Known Issues：正式目标账户 Prompt cursor 密钥/备份及发行信任、生产迁移、Server2025/Debian、Prompt 内容准入、Invocation 对RETIRED资格、Gate3/UAT/可用包未验。Next：`AI-04-A01` AI Task/Invocation 冻结边界与前置核查；Prompt增版/激活正式挂载维持阻塞。
