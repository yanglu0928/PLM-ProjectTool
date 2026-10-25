# PLT-PKG-01-A09-P51-A03：当前候选包内迁移与HTTPS隔离运行

日期：2026-10-25；状态：`SYNTHETIC_CURRENT_APP_PACKAGED_MIGRATION_HTTPS_PASS`。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；当前 WBS：`PLT-PKG-01-A09-P51-A03`。
- 输入基线：最新干净源提交 `c2ec928a4c67007c05bf7de18dbfb6d8bab95ac6` 派生候选 SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；P51-A02 清洁解包/原子文件落地通过；CR-PKG-011。
- 前置：`tools/smoke_current_app_packaged_migration.py` 与 `tools/smoke_current_app_packaged_https.py` 已用于 P47 当前应用族；当前候选身份在独立stage verifier允许列表中。P51-A02的 stage 与安装演练布局位于 `D:\PLMToolTemp` 直属 ASCII 临时目录。
- 涉及模块：仅包内一次性 Python/PG18.6/Caddy/HTTPS/合成 License 启动验收；不改产品程序、API、ORM、Migration、配置模板或服务注册。
- 实体/数据：只使用脚本创建的一次性空库和一条合成旧行，不导入项目/客户文件或客户数据。License/Secret仅为隔离测试临时材料。
- 权限：匿名/错误Host/Origin/无License项目拒绝，合成管理员登录与会话路径正向验证；不得声称正式License公钥、License信任或用户账户已部署。
- 验收：候选SHA前后固定；当前候选在包内 Python/PostgreSQL 18/pgvector完成空库和既有合成行迁移验证；包内 HTTPS 合成登录/Session、无License业务访问拒绝通过；进程全停、PG临时数据目录与测试Vault目标清理，端口回收；release/legal 标志不变。
- 风险/回滚：服务仅绑定loopback，使用临时端口/目录，不注册SCM、不触碰 `C:\PLMTool` 或现有数据库；系统若预占端口或临时Vault目标非空则停止，不清理任何未知内容。`release_eligible=false`、`legal_clearance=false` 永远保持。

## 执行顺序

1. 先对当前固定候选运行隔离 PG18/0185 Migration empty + synthetic-existing-row 验证。
2. 再运行已有 current-app packaged HTTPS smoke，使用新唯一的 pristine/target 临时路径；读取完整清理结果和候选SHA。
3. 对精确临时目录、临时Vault目标及测试进程作独立清理检查；失败则记录并修复验收工具，不降低正式信任边界。

这项只证明 Windows 11 非发行技术路径可运行，不证明真实License、安装可交给用户、三平台、法律、完整UAT、Gate或Pilot通过。

## 实际执行与偏差

- Migration：最终命令 `SYNTHETIC_CURRENT_APP_PACKAGED_PG18_MIGRATION_PASS`；固定候选 SHA 未变，包内 PG18.6/pgvector 0.8.6，`20261024_0185` 空库升级、synthetic existing row 保留、可控 downgrade/re-upgrade 通过；没有接触现有数据库，`release_eligible=false`。
- 首次传入尚不存在的临时目录作为 `--root`，工具要求该参数是已清洁提取的候选根，故失败于输入前置，无数据库初始化。第二次创建了空目录但参数语义仍错误，工具因路径不等于 `plm-current-app-stage-*` 既有提取根而拒绝；该 AI 创建的精确空目录经检查为空后删除。随后改用本次已验 stage 根，Migration PASS。无测试断言失败/无未知数据清理。
- HTTPS：`SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`；在包内 Python、PG18、Caddy loopback/HTTPS 下 synthetic login=200、Session=200、未授权License项目=403；临时生成的 synthetic public key 仅进入临时布局，绝不进入候选；48个临时凭据目标均清理，API/Caddy/PostgreSQL进程停止，测试文件/临时库已清理，脚本复核候选未变。报告字段 `formal_trust_provisioned=false`、`legal_clearance=false`、`release_eligible=false`。
- 外层复核候选 SHA-256 仍为 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；P51-A02的stage与atomic file placement目录暂留供后续隔离包验证。没有真实客户数据/事实、SCM或正式安装根参与。

## 结果与限制

`PLT-PKG-01-A09-P51-A03` 仅以合成技术数据证明最新 Windows 11 非发行候选随包迁移与HTTPS登录失败关闭链可运行；前端完整真实业务链仍需对这份新候选独立复验。真实公钥/License、操作员签发与备份仪式、正式服务账户/ACL/安装升级、法律放行、AI质量、UAT、Gate 3～7、Windows Server 2025及Debian 13均未关闭。候选不是可对外/正式交付包。
