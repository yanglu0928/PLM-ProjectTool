# PLG-04-A03：受控本地安装物化与宿主证据结果

- 日期：2026-11-06
- CR：CR-PLG-017
- WBS结论：PASS_SCOPE_LIMITED
- Hosted run：[42110700182](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42110700182)
- A17 job：127545475249；验证运行于GitHub hosted Windows Server 2025的D盘临时根。

## 实现

1. 新增未装配的 `LocalPluginInstallationMaterializer`：重验精确登记ZIP签名/Manifest/摘要，按installation UUID写入 `plugins/installations/<UUID>`；限制包体和ZIP成员沿用Inspector边界，逐成员SHA-256验证后以同卷no-replace目录提升。
2. 对同ID重试只接受成员集合、目录结构和逐文件内容均完全匹配的现有目标；额外文件、修改文件、链接/reparse point、特殊文件和未知目标均拒绝，不覆盖或自动递归删除。
3. Host evidence DTO增加可选 `plugin_installation_id`；只有Installation Owner记录新安装时强制Host evidence逐项绑定本次command UUID。现有Runtime Revalidation仍按其既有契约运行，不要求不存在的新安装ID。
4. A17 hosted PG18验证真实合成签名包逐文件物化、幂等重放和Owner写入Installation/RuntimeValidation/Audit；第二个隔离目录被改写后，Host proof失败，PG中无Installation/RuntimeValidation/Audit。
5. 未接HTTP、Worker、default composition或插件执行；不安装依赖、不导入/运行插件代码，无Schema/Migration/API变化。

## 独立验收证据

本轮最终run中，后端全量4,078项与wheel、前端测试/build、A17 harness语法、PG18/pgvector sidecar、clean parent PG18、嵌入式运行时与父包、A35、P24/A50、A17、A34均通过。A17结构化summary含以下证据：

- `PLG_04_A03_PG18_PASS`：签名合成包在精确Installation UUID目录逐文件复验，Owner保存绑定UUID的proof。
- `PLG_04_A03_TAMPERED_HOST_ZERO_FACTS_PG18_PASS`：有效归档之后检测到落盘成员被改写，未生成Installation/RuntimeValidation/Audit。

P25独立HTTP/Edge验收仍因hosted Windows `initdb.exe 0xC0000135`失败；因此整个run非全绿。这不影响A03专属PG18断言，但不构成Pilot或整体Gate通过。

## 范围限制与剩余风险

- Runner实际OS是Windows Server 2025；`windows-11`仅为合成RuntimeSnapshot，未在Windows 11实机验证，也不得推断Win11真实兼容。
- publisher正式信任源、服务账户正式ACL/data_root权限、插件执行隔离与默认装配均未验证/提供；生产安装仍关闭。
- 文件系统与PG事务非原子。Owner/Audit失败时保留目录，仅可通过同ID精确复验重试；未知目录和残留staging不会被自动删除。
- 首轮Hosted偏差及修复已按时间顺序登记于CR-PLG-017：Windows `DirEntry.stat` 硬链接计数缺失、A17安装清单硬编码包成员数、A03完成标志漏接。每项均通过后续Hosted复验确认修复。

本结论仅关闭PLG-04-A03限定WBS。Pilot、Gate 3及正式多平台Release仍未通过。
