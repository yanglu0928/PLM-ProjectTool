# CR-EXEC-019：修复 A17 合成 Document 固定来源夹具

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：hosted run 40811860032 的基础作业、父包组装/投影及父包 PostgreSQL 生命周期均通过；A17 已通过包内 HTTPS、Workflow GET/START/重放/CSRF/冲突/Audit 和 Windows 控制台输出，随后在创建合成 Solution SectionVersion 时返回 `SOURCE_UNAVAILABLE`。验证栈定位到 `SectionDocumentContentProofAdapter` 的固定文件证明。审查 P51-A05 合成 Document 夹具发现 `storage_locator=projects/<project>/prototype-input.txt` 不符合 `LocalFileStorage` 的受控 locator 格式（要求 `projects/<project>/objects/<bucket>/<file-object-uuid>`）；A17 又把文件写在 `data_root/private-documents/<locator>`，而 adapter 从 `data_root/<locator>` 读取。该问题阻断 A17 业务链，不能归因为产品服务或记作通过。
- 方案比较：A. 将 synthetic FileObject locator 改为存储 adapter 的规范对象路径，并将 synthetic 字节写入隔离数据根下 locator 指定的确切位置，验证存储内容 Hash/大小与 DB 元数据一致；B. 放宽生产存储 locator 校验以接受测试路径。选择 A，不改变生产安全边界。
- 基线差异：只修正 P51/A17 hosted 验证夹具中的合成存储路径与字节准备；不改产品存储实现、数据库 Schema、API、安装目录或用户数据。
- 影响与风险：P51-A05 与 A17 共用一个 Document fixture，需保持其测试数据内容 Hash、size 与元数据一致；写入只发生在本次 hosted run 创建的 disposable data_root，清理由现有 runner lifecycle 承担。
- 回滚：恢复旧 synthetic locator 和夹具行为；仅影响验证工具，不触及正式存储。
- 验证计划：托管 Windows 2025 执行后端/前端及 A17 全量链；要求固定 Document 下载证明通过、PlanVersion Edge markers、PostgreSQL 状态与清理/完整性 markers 均产生。未达全量 markers 不关闭 A27。
- 执行边界：仅 GitHub hosted runner，不在用户本机或 C 盘运行项目代码；只使用合成数据，不外发客户资料或 Secret。
