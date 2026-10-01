# PLT-PKG-01-A09-P48-A01：当前应用候选发行门禁差异复核

日期：2026-10-02；Phase 2；结论：`TECHNICAL_NON_RELEASE_CANDIDATE_PASS / RELEASE_BLOCKED`。本项只读复核新候选与 P46-A01 旧候选发行阻断清单，不生成法律意见或 Gate 通过记录。

前置输入：CR-PKG-008、新候选固定 SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`、[构建/清洁解包](plt-pkg-01-a09-p47-a03-current-app-candidate-extract.md)、[随包迁移](plt-pkg-01-a09-p47-a04-packaged-migration.md)、[合成 HTTPS](plt-pkg-01-a09-p47-a05-packaged-https.md)和[旧版发行阻断](plt-pkg-01-a09-p46-a01-release-blocker-register.md)。只读 ZIP 检查得到 `kind=WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE`、来源提交 `6d731177aacb1cfd1ae57fa01ce99275fea49e24`、载荷21,178、迁移0052存在，而 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`；ZIP根和产品级路径均无 `LICENSE`/`NOTICE`，运行时自身的许可证文件不能替代产品声明。

|门禁|新候选实际证据|状态/下一证据|
|---|---|---|
|应用字节/Windows 11合成运行|当前 wheel/dist 派生、全量哈希、包内迁移、合成 HTTPS/登录和无License 403|技术候选范围 PASS；不外推正式安装|
|第三方许可与产品声明|原父包 Caddy/Go/Ghostscript/OCR 审阅输入保留；产品 LICENSE/NOTICE 缺|法律归属/对应源码及最终声明审阅 OPEN|
|正式 License/信任|仅合成公钥与临时 Vault；正式材料未嵌入|真实工作台签发、公钥/目标账户恢复和 License 验收 OPEN|
|Windows 11安装/升级|仅 Temp 布局，未写正式根/SCM/现有库|离线新装、重启、升级/回滚与性能 OPEN|
|Windows Server 2025/Debian 13|Server VMnet8 阻断，Debian 用户暂缓验证|均不得从 Win11 推定 PASS|
|Evidence 交互/AI质量/UAT|前端合同测试与后端/PG 合成链有记录；真实浏览器工具不可用，POC03门槛未过|浏览器、独立质量留出集及 UAT OPEN|
|Gate 3～Release|无完整 Regression/Installation/Upgrade/Permission/Performance/Plugin/AI-RAG 报告|保持 OPEN，不发布当前 ZIP|

下一项只准备可审阅许可归属/产品通知缺项和正式信任/安装输入，不擅自给出法律签核；浏览器工具恢复后补 Evidence 实际 UI。当前二进制在 Git 忽略区，本项仅将程序构建/验证工具、追溯与版本说明同步 GitHub，**尚未向 GitHub 发布可使用发行包**。C盘首个解包暂存由于删除命令遭环境策略拒绝仍在，本项不绕过策略、不当作发行阻断已解决。
