# CR-PLG-016：安装事实要求归档内容复验

- 日期：2026-11-06
- 状态：PASS_SCOPE_LIMITED（PLG-04-A02 Owner与托管专项验收完成；P25独立诊断仍阻塞）
- WBS：PLG-04-A02
- 来源：PLG-04-A01 PASS_SCOPE_LIMITED后的安装事实接线核查
- 适用基线：Gate 2冻结PLG Package/Installation模型；承接CR-PLG-007、CR-PLG-009、CR-PLG-015
- 执行边界：只在GitHub hosted Windows runner D盘或云端沙箱执行；不在用户本机/C盘运行

## 发现

PLG-04-A01已将已登记签名ZIP私有持久化并实现 `LocalPluginPackageArchiveEvidence`，可验证精确包字节、摘要、签名、Manifest身份/版本和登记快照；当前该只读适配器尚未接入 `PluginInstallationOwner`。Owner现有Host evidence仅证明目标包已存在于主机并兼容，缺少对产品已登记包归档本身的独立核验。因此即使Host adapter报告存在，若私有归档缺失/损坏/签名或Manifest与数据库事实不一致，仍可能记录Installation事实。

## 决策与范围

在 `PluginInstallationOwner.record` 中先按数据库返回的不可变Package事实运行包归档证据Port；必须精确匹配PackageId、PluginId、Version与SHA-256且 `present_and_verified=true)，再检查现有Host安装/兼容证据，最后同事务记录Installation、RuntimeValidation与Audit。

归档完整性不代表物理安装：不得把归档存在映射为 `installation_present` 或兼容性，不得绕过既有Host evidence。无归档、归档证据失配或Host安装事实缺失均失败关闭，且不写Installation/Audit。

## 基线差异、风险和回滚

- 仅扩展内部DTO/Owner依赖和Repository映射；不改DB Schema/Migration、API、安装状态枚举、公开Composition或正式publisher trust。
- 所有包身份/签名/Manifest字段从已验证不可变Package row读取；证据只返回摘要与ID，不返回正文/路径。
- 先验归档，再取Host evidence，避免在归档失效时产生任何Installation事实；任何后续DB/Audit错误仍按现有UOW回滚。
- 回滚时可撤下Owner新增Port并恢复旧调用；不删除已存包和既有Installation历史，不把“无归档”降级为可安装。
- 生产publisher trust仍为空；合成测试不构成正式信任或运行许可。

## 编码前检查与验收

- 复核Package row已有全部不可变元数据，无需Migration。
- 单测覆盖归档缺失、错PackageId/hash/version/pluginId拒绝且Host Port不被调用；归档证据通过后仍必须存在精确Host安装/兼容证据；Audit失败全回滚与精确重放不变。
- PG18/A17合成验收调用真实Owner、Repository、archive evidence和合成Host evidence，确认有效归档+有效Host evidence才允许记事实；归档损坏/签名不匹配/缺Host evidence均零写。
- 后端全量/wheel、父包PG18 smoke、A17/A34/A35/P24/A50 hosted workflow；P25独立状态报告。
- 最高PASS_SCOPE_LIMITED；不解压、不安装依赖、不启动Plugin subprocess，不表示Win11实机/Gate/Pilot/Release通过。

## 编码前核查结论

PASS_WITH_LIMITATION。Package ORM已包含package_version、hash、Manifest snapshot、signature、signer key ref、compatibility policy及VERIFIED状态；现有Repository可在同一读取中提供这些字段。Owner现有Host evidence仍独立检查精确已安装SHA、兼容性和Runtime Snapshot。方案只增加一个先行归档复验，不改变这两个证据的含义，不扩Schema/API。

## Hosted 验收偏差（修复前记录）

- 2026-11-06 hosted run [42074467159](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42074467159) 后端全量测试的4,073项中有8项因 `test_plugin_runtime_revalidation_owner.py` 仍以PLG-04-A02前的4参数构造 `InstallablePluginPackage`，新增必需包版本/签名/签名者/兼容策略/验证状态字段后，在测试setUp阶段报TypeError；因此本轮产品代码尚未通过后端全量验收。
- 影响范围：运行时复验单元测试夹具陈旧；不是PG18验收结果，也未证明A02安装Owner路径通过或失败。A02 PostgreSQL端到端验证需在新的hosted run确认。
- 修复方案：只更新合成测试夹具使用与Owner契约一致的完整Verified Package元数据；不放宽产品验证、不更改运行时复验逻辑。修复后重新跑完整托管验收；如再出现独立失败，先记录再处理。

- 2026-11-06 hosted run [42075989085](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42075989085) 的A17 PlanVersion Edge/PG流程通过，但父包clean PostgreSQL smoke在既有 `validation/plg-02-a06-operation-disable/verify.py` 调用Owner时停在构造阶段：接口新增必需 `archive_evidence`，该旧验证器仍未注入；因此本轮A06后续PG断言被跳过，不能据此称该验证器或全workflow通过。
- 修复前处理：先保留此偏差记录，再只调整A06合成验证器：将本轮刚登记的签名ZIP保存到RUNNER_TEMP下的临时私有存储，使用真实只读归档校验适配器注入Owner；不改变A06产品逻辑或生产主机证据语义。重跑托管完整验收。

- 2026-11-06 hosted run [42080494651](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42080494651) 的后端/前端、父包和A35前置均通过；clean PG smoke中的A06主安装记录先通过，但后续API安装复用同一Owner时，验证器的 `TemporaryDirectory` 已退出，归档证据按预期失败关闭，导致A06后续测试未完成。此为测试夹具生命周期过短，非产品验证器异常。
- 修复前处置：保留本记录后，将合成归档临时目录延长至整个A06 PG18场景的finally清理点；确保两次Owner记录都使用同一真实归档适配器和受控D盘临时字节。重跑完整Hosted链路。

- 2026-11-06 hosted run [42082726109](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42082726109)：后端/前端、PG18 clean smoke、A17、A35、A34均通过，唯一失败为独立P25的initdb环境诊断。A17候选源码包含A02真实PG Owner/Repository/archive adapter调用与成功/三类失败关闭断言；A17 job成功且无异常，但其嵌套回调的专用marker未进入最终artifact marker列表，降低了专项结果的可见性，故暂不据此关闭A02。
- 修复前记录：只增强A17 harness结果可见性：在A02子探针成功返回后写入内存完成标志，并在外层A05 runner返回后输出一个受该标志保护的A02摘要marker；不重复调用Owner、不改产品代码或业务判断。重跑Hosted验证并确认artifact/log能显示该专项marker。

- 2026-11-06 hosted run [42086074649](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42086074649)：A17/PG18正反例探针和clean PG smoke通过，且A34成功；但在入口的直接marker仍被A05 runner的结果采集边界吸收，最终marker列表未显式包含A02专项结果。源码执行到A17 PASS_LIMITED且无异常，但按预定可审计性要求不关闭A02。
- 进一步修正记录（编码前）：A02成功后置位内存状态；在A05 `runner.smoke()` 返回的结构化结果 `markers` 列表中追加固定A02 PASS标记，并要求该标记确实注入后才允许验证器返回0。保持已有真实Owner/Repository/归档适配器和失败关闭断言不变，仅提升验收记录可见性。

- 2026-11-06 hosted run [42086074649](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42086074649) 的外层 A17 marker 列表仍未接收直接 stdout 摘要；复核 A05 入口确认其最终 artifact 只序列化 `runner.smoke()` 的结构化返回值。本次调整前记录：不再依赖嵌套回调 stdout；包装该次 A05 runner 返回结果，在且仅在 A02 PG18 探针已完整结束后，将专项 PASS marker 加入 `result["markers"]`，并检查注入标志与探针完成标志均为真，否则失败。仅验证器结果采集变更，不触碰产品判断、数据或用户本机。

- 2026-11-06 hosted run [42089880164](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42089880164)：A02真实PG18探针已输出有效归档+Host evidence成功，以及损坏归档/签名失配/缺Host evidence三类零事实失败关闭marker；随后A17包装器失败，因为A05 `runner.smoke()` 返回的结构化dict没有 `markers` 字段，先前直接索取既存列表不符合真实返回契约。失败仅在测试汇总层，非产品Owner或PG断言失败。
- 修复前记录：在A05返回dict中创建验证专用 `markers` 列表并追加A02专项marker，让A05现有JSON序列化输出该证据；同步将 `PLG_04_A02_PG18_PASS` 纳入外层A17 cloud validator的必需marker及摘要过滤，确保缺失即失败、出现时进入summary artifact。只改变托管验收证据采集，不更改产品逻辑、业务事实、包数据或信任。


## PLG-04-A02 验收结论

- 2026-11-06 GitHub hosted run [42092840314](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42092840314)：后端全量测试/wheel、前端测试/build、PG18/pgvector sidecar、embedded runtime/父包重建、clean parent PG18 smoke、A35候选交接、A34离线替换/显式手动恢复演练、P24/A50通过；A17 job成功，结构化结果artifact含 `PLG_04_A02_PG18_PASS`。A17 PG18日志证实精确归档+独立合成Host evidence才写入Installation/RuntimeValidation/Audit；损坏归档、签名失配和缺Host evidence各自失败关闭且零事实写入。结论仅 `PASS_SCOPE_LIMITED`。
- 同一run的独立 P25 job 仍因 Windows hosted `initdb.exe` 返回 `3221225781 (0xC0000135)`、无 stdout/stderr 且未创建数据目录而失败；未启动真实 HTTP/Edge，未改变A02专项结论，但使workflow整体非全绿。按既有 `CR-OUT-021` 诊断边界保留，不将其归因于A02。
- 不改变Schema/Migration/API、默认装配、正式publisher trust或插件执行；无客户数据、本机/C盘运行或真实安装。Gate 3、Pilot、正式Release仍未通过。
