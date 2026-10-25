# PLT-PKG-01-A09-P51-A14：Windows 11隔离离线升级与人工恢复前置

日期：2026-10-26。状态：`PASS_SCOPE_LIMITED`（Windows 11隔离Temp目录；非发行候选）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A14`|
|依据|`CR-EXEC-002`（Windows 11受控内部试用优先、离线安装/升级为Pilot前置）；`CR-PKG-011`；P51-A02当前应用候选原子落地工具及P51-A03～A13当前包运行、权限和恢复证据|
|唯一问题|现有原子落地工具只支持全新空目标；是否有安全、可重复的离线升级路径，可在隔离Temp布局更新已安装payload、保留明确的数据/License/插件目录，并在失败时恢复旧版本|
|候选证据|旧包 `current-app-candidate-4eaa7f158bed` SHA-256 `4f090636986c5c2173a5fde48eb161a94e5ee285ce73a8deb529c8682e048f46`，来源提交`c1a44366f29deac66a488168e26deecc73ceb221`；新包 P51-A02 `current-app-candidate-96313d4e1215` SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`，来源`c2ec928a4c67007c05bf7de18dbfb6d8bab95ac6`。两者kind一致、均`release_eligible=false`、每包22,197文件；旧来源提交为新来源祖先。payload差异为新增45、移除45、变更6（其中4项运行程序/前端内容、2项wheel元数据），不是空升级。二者开发版本号相同，故只证明候选payload更新机制，不宣称SemVer发行升级。|
|当前已知边界|P51-A02确认`tools/install_windows_current_app_candidate_rehearsal.py`拒绝既有目标；只创建空`plugins/data/logs/license/runtime`目录，不提供升级演练。正式安装规则明确“无自动回滚，由实施团队人工恢复”，因此本WBS必须模拟人工备份/人工恢复，不实现自动产品回滚。正式根`C:\PLMTool`、SCM、数据库及真实用户数据均禁止触碰。|
|计划范围|使用上述两个已存在候选和独立临时ASCII Temp目录，先对旧包原子落地，再在隔离布局中升级`app` payload；为`data/config/license/plugins`创建只含本轮随机marker的合成状态，验证不变。新增工具提供人工备份与显式人工恢复动作，不修改产品安装器或P39旧流程，不把合成布局称正式安装。|
|验收标准|绑定两个固定候选SHA与完整payload清单；只允许本轮创建的精确ASCII Temp根，初始目录/所有权不符即拒绝；旧`app`人工备份后，新payload先完整落入同卷私有stage并逐件验哈希，再切换；`data/config/license/plugins`的文件名/内容/Hash在升级前后完全一致；注入准备阶段故障时旧app仍原样，注入切换后故障时显式人工恢复命令能恢复旧app且保留失败新app供检查；不自动调用恢复；未知目标/符号链接/路径逃逸/候选种类或Release标志不符必须失败关闭；最终清理只删除本轮拥有的隔离布局。|
|风险/回滚|运行中的程序/服务/数据库不在本WBS启动，升级动作只改owned Temp布局。失败使用单独人工恢复命令，符合既有发行规范；不得在捕获升级错误后自动恢复。任何数据库迁移/升级不在本WBS执行，版本迁移另设任务且需空库、有数据、降级/恢复方案。若Windows目录rename语义不能满足失败关闭/人工恢复，停在 precheck 并记录，不改正式安装工具。|
|预期文件|独立`tools/upgrade_windows_current_app_candidate_rehearsal.py`、对应单测、A14一次性验证器、本记录、`STATUS.md`、`CHANGELOG.md`。|

## 实施前步骤

1. 已确认上述两包具备同kind、祖先来源和实际程序payload差异；不以最近相邻但只差metadata的P06包冒充完整升级证据。
2. 检查Windows本地Temp目标卷/rename边界和发行规范的人工恢复要求；实施前记录差异、故障注入方案、人工恢复步骤和Secret扫描范围，再编码。
3. 单元测试拒绝已有/未知目录并覆盖每个切换故障点；最后用本轮随机synthetic marker验证状态保留，不读取或复制真实用户数据。

## 验收限制

通过仅表示Windows 11本机合成目录的文件payload离线升级与显式人工恢复路径成立；不表示数据库Migration、正式服务安装、正式公钥/License/法律信任、Gate、Pilot或发行通过。两包均只读使用，固定当前候选不得被覆盖或重建。

## 最终验收结果（2026-10-26）

- 新增 `tools/upgrade_windows_current_app_candidate_rehearsal.py`：绑定本轮所有权和两个候选SHA；只接受直接ASCII Temp根；完整校验当前app与已准备的新app后，在同一Temp卷将旧app移至 `.plm-current-app-previous/app`，再激活新app。故障时不自动回滚；单独的 `restore_previous()` 校验旧/新payload，将失败新app保留到 `.plm-current-app-failed/app` 后恢复旧app。未修改现有新装器、产品入口、服务、数据库或Migration。
- 五项标准库 `unittest` 通过，覆盖正常切换、准备后失败、保存旧版后失败、激活新版后显式恢复、所有权不匹配拒绝。`py_compile` 与 `git diff --check` 通过。
- Windows 11实际包演练复用旧/新候选既有完整性报告（归档SHA分别为 `4f090636…e048f46` 与 `3cbd68aa…f2326f455`；报告记录的归档大小与当前文件一致），从旧包逐件校验落地后执行新版完整payload复制/哈希回读；在切换完成后注入故障，结果为 `PLT_PKG_01_A09_P51_A14_PASS_SCOPE_LIMITED`。显式人工恢复通过，旧payload恢复，新payload留在失败隔离区；合成 `data/config/license/plugins` 文件名、内容及SHA快照不变。升级器没有自动恢复。
- **执行偏差记录：** 本机逐个读取约1.3GB归档和22,197个小文件耗时显著；最终复验复用了此前已生成且路径/大小/SHA相符的候选完整性报告，没有再次对两个ZIP全量计算SHA。归档内manifest/checksum/kind/release标志被读取核对，实际旧/新暂存payload在本轮复制时逐件与记录的SHA清单比对，目标落盘逐件复核。此方法不降低payload文件哈希验收，但A14报告不声称本轮重新计算了归档SHA。期间修正一次性夹具未先创建`config`目录及重复全树预扫描；中断的随机Temp演练根/partial经路径和归属核验后已清理，未触碰历史安装/阶段目录。
- 本轮只运行文件级合成演练；未启动产品服务、PostgreSQL、真实License/密钥、正式安装根或真实数据，也未执行数据库Migration。候选均保持 `release_eligible=false`、`legal_clearance=false`；版本号相同，因此只验证payload替换和人工恢复，不宣称对外版本升级兼容。

## 下一项

`PLT-PKG-01-A09-P51-A15`：先检查A14升级后候选是否可以在全新隔离Temp根完成当前应用启动与健康检查；限定合成环境，正式信任/安装和真实数据库仍不触碰。
