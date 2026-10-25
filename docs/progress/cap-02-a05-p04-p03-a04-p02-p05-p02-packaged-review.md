# CAP-02-A05-P04-P03-A04-P02-P05-P02：固定候选包内评审链

日期：2026-10-24；结果：`WINDOWS_11_SYNTHETIC_PACKAGED_REVIEW_PASS / NEGATIVE_MATRIX_PARTIAL / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `P05-P02`；仅在固定非发行候选内验证 GLOBAL Capability 固定版本受分配评审，不修改产品字节。|
|输入基线|`CR-CAP-005/006`、`DEC-20261024-CAP-P05-P02`、P05-P01 固定 SHA `f2a2385538b111a1a36e3761086e0f4e5749554a3c57bde8941c0fb11080e095`。|
|前置|P05-P01 清洁解包/包内基础链通过；A03-P02 源码环境 Edge/PG 通过。清洁暂存目录只读复用，两份新布局独立创建。|
|模块/实体/API/权限|仅新增验收夹具，走包内实际 HTTPS/PG/前端；无产品 ORM/Migration/API/角色变更。部署管理员建合成来源与资格，普通受分配 Reviewer 决定。|
|验收|固定双条目可见、未确认前按钮禁用、两人批准与批准指针/Audit；匿名、未分配、签名游标篡改拒绝；同包 SHA、进程/Vault/布局清理。|
|风险|测试许可/证书/账号均为一次性合成，真实客户确认与正式信任不能由此推定；失效 License、停用评审人和跨会话游标等扩展负例另片。|

使用固定候选重新完整核对 22,196 件载荷、两份 22,199 件布局；包内 PG18/API/Caddy/HTTPS 与工作流前置通过。真实 Edge 建立 GLOBAL 固定 Document 和 Baseline，再建立整文档 Evidence CANDIDATE；管理员经包内 HTTP 将其核为合成 `ELIGIBLE`，创建两个同源能力条目的 DRAFT Version，VALIDATE 得 `valid=true` 后送双 Reviewer 的内部 Review。此处合成资格不是正式客户事实。

匿名固定版本 GET 返回 401，已登录未分配者 Review/固定版本 GET 返回 404，签名分页游标篡改返回 400。受分配普通 Reviewer 在真实 Edge 登录，页面读到两个固定条目，未勾选时批准禁用，勾选后决定成功；第二 Reviewer 经独立 HTTPS 会话批准，Review 终态 `APPROVED`，Baseline 当前批准版本指针精确指向该 Version。隔离 PG 中两人各一条 `APPROVE` 决定、`REVIEW_DECISION_RECORDED` Audit 共 2。脚本退出 0；候选 SHA 前后不变，48 个合成 Vault 目标、包内 PG/API/Caddy/Edge 与两份布局全部清理。

验证范围只证明 Windows 11 当前非发行包在合成信任下可执行这一条完整 Capability 评审链。它不覆盖停用 Reviewer、到期/撤销 License、跨会话游标、不确定网络结果重试、正文一键定位、普通 Reviewer 待办发现、正式发行公钥/目标服务账户/CA、离线安装与升级、真人客户确认、完整纵向 UAT、Server2025/Debian13 或 Gate/Pilot/Release。下一片 `P05-P03` 补剩余包内拒绝/恢复矩阵；独立 P03-P02 仍需多条目写入与状态合同差异。
