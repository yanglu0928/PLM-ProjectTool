# PLT-PKG-01-A09-P41：离线新装统一命令门禁与隔离演练编排

日期：2026-10-01；状态：`NON_RELEASE_COORDINATOR_PASS / FORMAL_INSTALL_BLOCKED`。输入 P33 固定候选/P22 父包/P34 暂存、P38 正式门禁和 P39/P40 文件事务；未修改 Gate 2 冻结内容。

编码前检查：Phase 2/Gate 3 开放；前置文件、服务、证书、License 和法律条件不满足，故正式安装必须失败关闭。本项仅协调新装检查与非发行演练，不改实体/API/权限/Schema/Migration。验收是同一命令显式区分 `assess`、`install`、`rehearse`：前两者绝不写目标，第三者只能写新 ASCII Temp 目标并在发布后独立全量复验；正式门禁状态不能被任何模式改写。风险是把演练通过误称发行放行、校验器之间边界不一致或无意触碰正式根。

新增 `tools/windows_offline_install_coordinator.py`。所有模式先由 P38 核固定包与已有干净布局并报告真实阻断；`assess` 返回只读评估，`install` 即使收到伪造的准入标志也拒绝，绝不调用 P39。`rehearse` 调 P39 的同卷待发布/Hash/发布流程，随后再次以独立 `verify_layout` 校验目标文件数和映射 Hash；其结果始终是 `NON_RELEASE_REHEARSAL_PASS_FORMAL_INSTALL_BLOCKED`，不能作为正式安装证明。正式安装根、SCM、目标账户凭据、证书、License 或已有数据库都不由本命令供给/修改。

Windows 11 定向单元 6/6：评估只读、安装拒绝、隔离演练调用及后核、后核差异拒绝、前置失败不复制、伪造准入拒绝。真实固定包运行 `install` 返回 `FORMAL_INSTALL_REFUSED`/退出 1，列出账户、DNS/证书、公钥及六项未验门禁，正式根/SCM/DB 不变。真实固定包运行 `rehearse` 到新临时目录，21,115 件、P33 SHA `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`、映射 SHA `d4072ed23558da5026911fad3575ee8b4d67944814b58096b6587c1bf9908580`，独立布局校验通过，正式阻断仍保留。

兼容性：仅 Windows 11 隔离新装编排验证，Windows Server 2025 未跑，Debian 13 按用户要求暂缓实机；不改变生产 API、Schema、SCM 或发行包。升级说明：无迁移，不支持已有安装升级。回滚可不使用该编排工具，P38/P39/P40 原证据和目标数据不受影响。已知问题：没有可执行正式安装路径，目标账户、证书、License、NOTICE/Ghostscript 和平台 Gate 均开放；`release_eligible=false`。

下一项 P42：验证随包 Python 在合成且隔离的信任源和临时 PG18 下能以 `--platform-write` 启动并经包内 Caddy 处理真实登录/会话链；必须区分改造后的合成运行布局与固定发行候选，不能将测试公钥当正式信任锚。
