# PLG-04-A03：受控本地安装物化与宿主证据编码前检查

- 日期：2026-11-06
- WBS：PLG-04-A03
- 结论：PASS_WITH_LIMITATION，可实现未装配的内部本地物化/复验适配器；运行范围限GitHub hosted Windows runner D盘与隔离合成PG18。
- 基线/决策：Gate 2冻结PLG Installation Root与Package Root；CR-PLG-016已使Installation Owner先复验精确登记归档。实现前按CR-PLG-017记录内部Port与本地文件布局差异。
- 用户环境约束：禁止在用户本机或C盘运行；不接触客户数据。

## 源码盘点

1. `PluginPackageArchiveInspector` 已有有界、只读ZIP/Manifest/签名检查和路径规范化，但明确不解压。
2. `LocalFileStorage` 仅为精确签名归档提供 `plugins/packages/<package UUID>` 私有存储；没有本地安装目录或安装复验适配器。
3. PLG-04-A02 的 `PluginInstalledPackageEvidencePort` 是抽象Port，当前PG18只使用合成Host evidence；Production caller/安装流程尚未出现。Port未携带installation_id，不能精确绑定目标安装目录。
4. PLG-02-A02原始核查已明确没有安装文件部署执行器、安装API或运行时执行入口；PLG-02-A07读取API与A08停用API都不执行物理安装或卸载。
5. `plg_installations` 已具备immutable package FK、安装状态、RuntimeSnapshot和actor/time；当前不需要增加文件locator或新的业务Root/API。数据库事实不能单独证明文件已部署。

## 决定与范围（先记CR-PLG-017）

新增隔离的内部本地安装物化适配器，把仅已VERIFIED且签名/Manifest/包字节复验通过的归档安装到 `<service data_root>/plugins/installations/<installation UUID>`。接口必须携带 `installation_id`；安装包身份和数据库Owner调用保持一致。输出只含经过比较的安装SHA与最小RuntimeSnapshot，不回传路径/正文。只有安装目录被精确复验后，才能委托既有 `PluginInstallationOwner` 记录事实；Owner继续独立重验登记归档。

安全/恢复边界：

- 安装路径只能由合成/已验证UUID拼接，禁止归档输入决定目标路径；不跟随symlink/reparse point；拒绝绝对/UNC/驱动器路径、路径穿越、重复规范化路径、Windows大小写冲突和特殊文件。
- 复用Inspector既有压缩包上限/展开限制；逐文件流式展开，临时目录必须为目标同卷私有子目录，逐文件hash/size与输入ZIP成员比对后原子提升。
- 已有目标不覆盖/不删除：仅当目录无链接、文件集合与每一成员内容均和精确已验证归档一致时允许幂等复验；未知或不相关目标失败关闭并保留。
- Postgres写入失败不撤销或盲删安装目录；同一installation UUID重试先精确复验已有目标，随后重复调用Owner。任何身份/Hash/运行时或Owner验收失败均不记录Installation/RuntimeValidation/Audit。
- 本WBS只解压/物化为数据文件，不导入/执行插件代码、不安装第三方依赖、不启用Operation、不开放HTTP/Worker/default composition。正式publisher trust为空时生产组合仍不可用。

## 验收计划

GitHub hosted Windows Server 2025 runner D盘隔离临时根 + synthetic PG18：有效签名合成包文件逐成员等字节物化/原子提升/重放；zip-slip、UNC/drive、重复与大小写冲突、symlink/special-file、损坏摘要、错package/installation ID、无关既有目标以及Audit/DB提交故障拒绝或精确恢复；验证Host evidence确实与 `installation_id` 和每个落盘成员绑定，Owner仍要求独立归档和Host证据，失败无业务事实。不得将托管runner结果推断为Windows 11实机/正式服务ACL测试。

## 限制与回滚

不改Schema/Migration/API/正式trust/default app。安装物化是文件系统副作用，数据库不能跨资源回滚；只能重用同ID的verified exact target或人工诊断未知路径，禁止自动递归删除。若数据根生产ACL/发布信任/服务身份未满足，保留未装配适配器并失败关闭。具体CR-PLG-017规定风险、实现差异与验证计划。
