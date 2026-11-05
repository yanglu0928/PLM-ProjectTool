# CR-PLG-017：受控 Plugin 本地安装物化与精确宿主复验

- 日期：2026-11-06
- 状态：实施中；首轮Hosted复验发现并已登记Windows目录枚举证据差异，修正后重跑
- WBS：PLG-04-A03
- 关联：CR-PLG-007、CR-PLG-008、CR-PLG-012、CR-PLG-016；Gate 2冻结PLG Package/Installation模型和Plugin subprocess边界
- 执行边界：只在GitHub hosted Windows runner D盘或云端沙箱；用户本机/C盘禁止运行

## 发现

PLG-04-A02已使InstallationOwner先校验精确已登记ZIP归档，再要求独立Host evidence。源码盘点发现无本地安装物化适配器；现有PackageArchiveInspector只读复验，LocalFileStorage仅存归档。A02 PG18验证采用合成Host evidence，不能证明产品可从签名归档形成真实宿主安装目录。Owner evidence Port还未绑定installation_id，因此多个/错位安装目录无法被精确区分。

## 决策与范围

新增未装配的内部 `LocalPluginInstallationMaterializer`（具体类名可在实现时遵循仓库命名）和Host evidence适配器：

1. 输入必须是精确Verified Package identity与命令固定的installation UUID；Owner复核不可变数据库事实、签名归档和Host事实。
2. 重新读取并复验同一归档；以合成installation UUID作为路径唯一来源，在服务data_root下的 `plugins/installations/<installation UUID>` 生成同卷私有staging目录。仅物化ZIP中受Inspector允许的普通文件/目录；逐成员有限流式写入和hash复核；确认所有文件后同卷原子提升。
3. Host复验重新检查installation UUID目标无链接/特殊文件、文件集合与精确归档每一成员字节一致，并生成最小兼容RuntimeSnapshot；不运行入口脚本、不导入插件代码、不安装依赖。
4. 同ID精确目标可复验并重试；不匹配或无关目标不覆盖、不删除。Owner/UOW失败时保留目录；无事实写入，后续相同ID通过严格复验证明后方可恢复记录。
5. 本项不增Schema/Migration/API、不提供安装HTTP、不接Worker/default composition/Plugin execution/Operation enablement；无生产信任时任何正式安装组合仍关闭。

这是内部部署能力和Port identity 的可追溯实现增量，不改冻结公开合同或PLG DB Root。精确安装目录位置属于服务私有数据根，避免新增数据库locator/Host路径泄露。

## 编码前检查

- 冻结ORM已有Package/Installation状态与Snapshot，文件证据不需数据库字段。
- Inspector限制签名归档成员数量/压缩与规范路径；实现必须复用/收紧这些限制，不依赖抽取到临时路径后再信任。
- 同卷物化、无覆盖、未知目标保留；PostgreSQL与文件系统非原子，利用UUID重放与严格文件集合复验恢复。
- 只有持久签名信任/Service ACL正式来源供给后才可后续装配；本项不验证正式信任或ACL。
- 后端测试/wheel、file materializer专项、clean PG18 Parent smoke、A17 marker、A34/A35/P24/A50、Secret检查及GitHub同步。P25继续作为独立diagnostic，不得混为本WBS结果。

## 风险与回滚

- 文件物化后PG/Audit提交失败将留下可重复验证目录；保留文件而不自动删除，阻止失败安装被Owner登记。
- 压缩档成员大小/路径歧义可导致写入越界；要求先验证完整归档，再用同一规范化函数拒绝duplicate/case collision/links/special entries。
- 目标目录ACL和服务账号正式来源未供给；只做托管runner D盘受控合成验证，不宣称生产安全装配。
- 回滚代码只撤下未装配Materializer/Port适配器与内部Owner调用，不删留存目录/Installation历史，不改Schema/API。

## 验收

GitHub hosted Windows runner D盘临时数据根和隔离PG18，只用synthetic package/runtime identities。有效包准确安装/重放/PG Owner记录；zip-slip/UNC/drive/duplicate/case collision/symlink/special entry/hash drift/incorrect installation UUID/unknown existing target各失败关闭。验证失败时无Installation/RuntimeValidation/Audit，Owner既有Archive proof和Host evidence仍均必需。完成限定范围后最多PASS_SCOPE_LIMITED；无Win11实机/正式服务ACL/正式publisher trust/插件运行/Gate/Pilot/Release声明。


## 编码前澄清（2026-11-06）

在产品实现开始前补明证据契约：`PluginInstallationEvidence` 必须携带 `plugin_installation_id`，Owner须逐项匹配本次command的Installation UUID；仅Host adapter读取目录时带ID、而proof不回显ID不足以避免错目录证明。正向/错误ID/不存在目录测试均覆盖该绑定。该内部DTO强化属于本CR范围，不改DB/API。


## 首轮Hosted复验偏差（2026-11-06，run 42104195641）

- Windows Server 2025 hosted runner上，`DirEntry.stat(follow_symlinks=False)` 对新建普通文件返回 `st_mode=33206`、归档属性32且 `st_nlink=0`，使 materializer 把普通文件误判为无效类型；后端全套4078项中仅3项物化器用例失败。改为对枚举到的目标调用 `Path.lstat()` 获取完整本机文件状态，继续拒绝链接/reparse与多硬链接，不放宽安全断言。
- 新增证据字段对既有 Runtime Revalidation Host port 的兼容：`plugin_installation_id` 缺省可空；仅 `PluginInstallationOwner.record` 本次传入installation ID时强制逐字匹配，既有重验证不记录新的Installation ID。
- 该run未到wheel、PG18、A17；A03/A02均未验收。首轮改动已先记录，需通过修正后完整hosted run再判断。


## 第二轮Hosted复验偏差（2026-11-06，run 42104924949）

- 后端4,078项/wheel、前端/build、A17 harness语法、clean PG18/pgvector、embedded runtime、parent assembly、P24/A50/A35及A34均通过；A02正向归档/Host事实与A03损坏安装树零PG事实检查均实际通过。
- A17最后的A08文件清单断言仍使用A08原“归档+对象”计数，未把A03新增的 `plugins/installations/<UUID>` 文件加入预期；因此在A03 PG18探针已通过后，A17后续A08存储盘点断言失败。修正为从精确 `valid_archive` 成员动态推导安装树清单并独立核对原对象/归档计数。该问题只在验证器清单断言，不改业务代码。
- 独立P25仍因Windows hosted `initdb.exe 0xC0000135`失败；不是A03根因。run整体失败，A03不关闭，Pilot/Gate/Release状态不变。


## 第三轮Hosted复验偏差（2026-11-06，run 42107854567）

- A03物化器单测及PG18正向安装、UUID绑定和篡改后零事实拒绝均已通过；A08 PG18探针也通过。A17由于只设置A02完成标志，未设置A03完成标志，在最终结构化summary包装器处错误拒绝已完成的A03探针。
- 该问题属于探针完成标志漏接，不影响实际PG18断言；需将A03标志与A03 PG18断言的成功位置绑定，并仅在A02与A03两组断言均完成后输出summary marker。修复后再跑完整托管工作流。
- 同run其他结果：后端/前端、clean PG18、父包与A34均通过；P25独立 `initdb.exe 0xC0000135`诊断仍失败。A03尚未关闭。
