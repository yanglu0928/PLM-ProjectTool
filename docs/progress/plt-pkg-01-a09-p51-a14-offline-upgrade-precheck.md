# PLT-PKG-01-A09-P51-A14：Windows 11隔离离线升级与回滚前置

日期：2026-10-26。状态：`PRECHECK_READY`（非发行候选；尚未执行升级）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A14`|
|依据|`CR-EXEC-002`（Windows 11受控内部试用优先、离线安装/升级为Pilot前置）；`CR-PKG-011`；P51-A02当前应用候选原子落地工具及P51-A03～A13当前包运行、权限和恢复证据|
|唯一问题|现有原子落地工具只支持全新空目标；是否有安全、可重复的离线升级路径，可在隔离Temp布局更新已安装payload、保留明确的数据/License/插件目录，并在失败时恢复旧版本|
|当前已知边界|P51-A02确认`tools/install_windows_current_app_candidate_rehearsal.py`拒绝既有目标；只创建空`plugins/data/logs/license/runtime`目录，不提供升级/迁移/回滚。故不可直接对既有目录覆盖。正式根`C:\PLMTool`、SCM、数据库及用户数据均禁止触碰。|
|计划范围|先只读盘点本地可用的两个同kind Windows current-app候选及其manifest/文件清单/哈希谱系，再设计并实现独立的隔离升级演练器；不修改产品安装器或P39旧流程，不把合成布局称正式安装。|
|验收标准|必须绑定两个固定候选SHA与完整payload清单；仅允许精确命名的全新ASCII Temp试验根；保留原版本可验证快照和独立数据目录；正常升级后逐件哈希核验新payload且数据目录哈希不变；注入复制/校验/切换故障后原版本恢复且状态数据不变；未知目标/符号链接/路径逃逸/候选种类或Release标志不符必须失败关闭；最终清理只删除本轮拥有的隔离目录。|
|风险/回滚|原子双目录或同卷切换若不能在Windows实现可靠回滚，不修改原子安装工具；保留失败证据并转向不依赖升级写路径的任务。任何数据库迁移/升级不在本WBS执行，版本迁移另设任务且需空库、有数据、降级/恢复方案。|
|预期文件|独立`tools/upgrade_windows_current_app_candidate_rehearsal.py`、对应单测、A14一次性验证器、本记录、`STATUS.md`、`CHANGELOG.md`。|

## 实施前步骤

1. 只读确认至少存在两个完整、可校验且manifest kind一致的候选；保存候选SHA、manifest版本、来源提交和payload差异摘要。若无合格旧候选，停止编码，先确定不伪造的候选来源。
2. 检查Windows本地Temp目标卷/rename边界和现有P39隔离恢复记录；先记录实施偏差、失败注入方案、回滚步骤和Secret扫描范围，再编码。
3. 单元测试拒绝已有/未知目录并覆盖每个切换失败点；最后用最小 synthetic marker 验证数据保留，不读取或复制真实用户数据。

## 验收限制

通过仅表示Windows 11本机合成目录的文件payload离线升级/回退路径成立；不表示数据库Migration、正式服务安装、正式公钥/License/法律信任、Gate、Pilot或发行通过。固定当前候选 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 不得被覆盖或重建。
