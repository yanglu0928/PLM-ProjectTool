# PLT-PKG-01-A09-P51-A44：父包内非秘密 Pilot 就绪报告与组合验收结果

- 日期：2026-11-02
- 状态：PASS_LIMITED
- 编码前检查：plt-pkg-01-a09-p51-a44-readiness-tool-bundling-precheck.md
- GitHub Actions：[run 41376505925](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925)
- PR #61 head：f182eb37cb572da99b6615746655d7c7a0e2b30c；本次 workflow merge commit：325ce2e90b298d657ca3acceb98bcb8a54968abe。

## A44 交付

- Windows 父包新增非秘密 Pilot 登记示例、PowerShell 报告入口和随包 readiness report/validator。入口使用候选内嵌 Python，读取包 manifest 与外部指定登记 JSON，不写回候选、manifest或清单。
- 报告列出登记缺项与固定阻断码，不输出登记值。9 个缺项输出正确；使用合成完整登记时仍为 COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION，pilot_ready/launch_authorized 均为 false；加入未知字段及合成敏感哨兵后拒绝且未回显。
- 父包实际清洁解包 smoke 在 hosted D 盘成功；A44 报告状态 PACKAGED_PILOT_READINESS_DIAGNOSTIC_PASS_LIMITED，manifest/checksum未变化。报告资源纳入父包逐文件哈希。

## 同 run 组合证据

- 12/12 workflow jobs success：后端全量测试/wheel、前端测试/typecheck/build、固定来源 Python 3.13.15、PostgreSQL 18.6/pgvector 0.8.6、embedded backend、父包构建、D盘清洁解包与PG生命周期、A17、A34 均成功。
- 父包内部 ZIP SHA-256：8e3e4e37224ad3653c2f2d758d024e23a5c6591fde89cb85efd375bc304f801d；payload 20,122 个文件。Artifact ID 13111846328，372,790,641 bytes；artifact 容器 digest SHA-256 879356d6214c6ef35b8cdfa56ac4789b861c2dfcaccb381d99fc5f832b27f0a4，保留至 2026-11-16。
- A17 PlanVersion Edge/HTTPS/PostgreSQL：29 次 API 操作，状态 IN_REVIEW，WBS/requirement/validation=(2,2,1)，Review/Round=IN_REVIEW，customer decisions=0，synthetic identities=true；candidate SHA-256 2f1503eff018be183b054207a35615d9c4f92158a949df43f8c3257caa3e3fb4；证据 artifact ID 13112435419。
- A34 D盘隔离替换/失败候选隔离/明确手动恢复通过；old/new payload 分别 20,119/20,122 项，candidate quarantine 与 explicit restore 均 true；状态 PLT_PKG_01_A09_P51_A34_PASS_LIMITED。

## 偏差、修复与限制

- 首轮 A44 wrapper 把内嵌 Python 路径写错为 payload/runtime/python/python.exe；hosted 分类退出码 2、stdout 0、stderr 51 bytes。先记录后更正为 payload/runtime/python.exe。
- 下一轮 A17 projection 拒绝新增父包专用报告文件。先记录，再将启动报告、readiness wrapper/工具和登记模板共5个父包专用路径纳入精确投影排除，并增加“只排除已知项、未知未来项仍拒绝”的测试。新同 run A17 全部通过，父包原始逐文件哈希仍完整校验。
- 环境仅 GitHub hosted Windows Server 2025；没有 Windows 11 新实机测试。未安装产品，未启动服务/正式数据库/API，无listener、无客户决定。
- 正式产品公钥/License trust、DB凭据身份、服务账户/ACL、TLS和法律放行仍缺；release_eligible=false、legal_clearance=false、formal_startup_ready=false。A44 不代表 Pilot、Gate 3 或 Release 通过。Artifact 可从 run 页面下载，有效至 2026-11-16。

下一项：PLT-PKG-01-A09-P51-A45，扩充包内 readiness 报告的逐字段填写指引与下一步操作提示；报告仍保持非授权性。编码前先检查并追溯记录。