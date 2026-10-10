# WFL-01-A08-P07：当前 Workflow 候选持证外部 HTTPS 验证

2026-10-02 / Phase 2 / `SYNTHETIC_PACKAGED_WORKFLOW_HTTPS_PASS`。输入是固定 Windows 11 非发行 ZIP SHA-256 `6b0cd4978d5526554443d6ab1b0528ddd4c2feebfa7690c41af627fe55887acb`、P05 全量清洁解包/包内 ASGI-PG18 矩阵、P06 基础外部 HTTPS。按 `DEC-20261002-601` 仅扩展已有合成烟测工具的成对回调：签名私钥仅在测试进程内瞬时生成并于启动前释放引用，合成公钥只注入可清理的第二安装布局；不改固定 ZIP、产品代码/Schema/API/依赖或正式账户。

定向防护单元 5/5、脚本语法检查及 `git diff --check` PASS。工具先拒绝回调不成对和空签名文档，再逐件核固定候选/暂存和两份隔离布局。21,182 载荷加 3 元数据均符合布局校验。包内 Python、PG18.6、Caddy 与合成当前账户 Vault 启动后，经真实 `https://localhost`：基础登录/会话 200、无 License 项目 403、错误 Host/Origin 拒绝；种入临时数据库中的**合成有效签名 License**、经理成员与未启动 Workflow 后，GET 初态 200/`"v0"`/六阶段，缺 CSRF 的启动 403，首次 POST `workflow:start` 200/`"v1"`/HANDOVER，同 Key 重放 200 且首次固定结果相同，另一 Key 冲突 409，再 GET 当前状态 200/`"v1"`。数据库只有一份 `WORKFLOW_STARTED` Audit 和一份 `V1_WORKFLOW_START` 收据，StageTransition 为零。测试 exit 0；ZIP SHA 不变、12 个合成 Vault 密钥/数据库凭据与临时进程/目录清理 PASS，事后无 P07 布局或 Caddy/PostgreSQL 进程。

这证明 Windows 11 本机合成信任下包内 Workflow GET/START 的外部 HTTPS 网络链，而**不**证明真实浏览器页面、正式发行公钥/License 仪式、目标账户材料、Server 2025/Debian 断网安装升级、法律合规、AI 质量/性能/UAT/Gate 3。固定候选仍 `release_eligible=false`、`legal_clearance=false`，不得作为交付包。下一独立任务回到 Workflow Checklist 实际 Owner 前置，或继续其他不依赖真实浏览器/正式信任的 Phase 2 能力；浏览器工具恢复后必须补 P06 UI 验收。

兼容/升级/回滚：无产品 Migration、新 API 或依赖，现有安装不触碰；测试扩展点默认不启用，撤去回调即可恢复基础烟测，历史证据与候选不覆盖。正式升级仍需备份、维护、迁移和恢复演练。
