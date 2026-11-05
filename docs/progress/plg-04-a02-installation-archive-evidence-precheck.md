# PLG-04-A02 编码前检查与验收范围

- 日期：2026-11-06
- Change Request：CR-PLG-016
- 结论：PASS_WITH_LIMITATION，可开始编码
- 审计方式：只读GitHub源码
- 程序执行限制：仅GitHub hosted Windows Server 2025 runner D盘或云端沙箱

## 单一问题

PLG-04-A01已建立已登记签名ZIP的私有存储与只读复验适配器，但PluginInstallationOwner只检查独立Host安装/兼容证据，未验证登记包的私有归档。当前安装事实缺少“签名归档仍与不可变数据库Package事实一致”的先行检查。

## 证据

- ORM `plg_packages` 已含 `plugin_package_id`、normalized plugin id、version、SHA-256、Manifest snapshot、detached signature、signer key ref、compatibility policy和package_state；无新增列需求。
- `SqlAlchemyPluginInstallationRepository.find_verified_package` 当前过滤VERIFIED，但DTO仅返回id/plugin id/hash/Manifest；可只读扩展为完整不可变身份快照。
- `LocalPluginPackageArchiveEvidence` 已用摘要绑定读取、现有Inspector重验ZIP签名/Manifest，并与PackageIdentity全部快照比较；返回metadata-only evidence。
- Owner现有 `PluginInstalledPackageEvidencePort` 独立证明目标机上的包SHA/存在/兼容和受限Runtime Snapshot；不能以归档存在代替它。

## 方案与安全边界

扩展 `InstallablePluginPackage` DTO携带从锁定Package row读取的签名、signer key ref、Version、兼容策略及 VERIFIED状态；Owner先将其交给归档证据Port，并匹配PackageId/PluginId/Version/SHA，再调用既有Host evidence。无归档或不匹配立即失败，Host adapter不会被调用；只有两类证据都匹配才写Installation、RuntimeValidation和Audit。精确重放行为不变。

不增加DB migration/API、不装配公有路由/Worker、不创建安装文件、不解压依赖、不启动插件。测试使用synthetic signer/archive与合成Host runtime。生产publisher signer仍为空；缺少真实归档或Host安装事实均不生成Production Installation事实。
