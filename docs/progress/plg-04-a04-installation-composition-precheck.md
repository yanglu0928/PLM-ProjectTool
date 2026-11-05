# PLG-04-A04：Installation生命周期接线编码前检查

- 日期：2026-11-06
- WBS：PLG-04-A04
- 结论：BLOCKED_BY_PREREQUISITE；当前不向默认组合或HTTP/Worker接入物化器。
- 基线：Gate 2冻结Plugin/API/数据库边界；A03按CR-PLG-017以PASS_SCOPE_LIMITED完成。
- 执行边界：仅读GitHub仓库；无本机/C盘代码、客户数据或真实信任材料。

## 源码核查

1. `create_app`只可选装配包导入、安装元数据和停用Router，没有安装创建HTTP Router；冻结API也没有可直接复用的安装命令入口。
2. Windows package Worker仅做签名包导入/注册和归档持久化，不依赖A03安装物化器，不会创建/执行插件。
3. `PackagedPluginSignerResolver`只从随包只读trust manifest解析ACTIVE key；A17已经断言该manifest的keys为空。没有正式发布者公钥时，生产包导入/安装均无法通过真实签名信任。
4. A03 materializer仍是未装配内部适配器；其LocalFileStorage根检查可拒绝链接/reparse，但不会为服务账户创建或验证正式NTFS ACL。仓库没有可证明生产data_root ACL的部署身份来源。
5. 现有Activation Owner只写数据库状态/Audit，不物理启停文件或执行插件；不能将数据库启用事实当作可运行安装。

## 决定

当前两项前置缺失：正式publisher公钥/信任清单管理来源，以及Windows服务账户data_root ACL/安装根生命周期来源。由AI生成或从合成Key推导生产信任会虚构信任主体；在托管runner合成ACL或凭当前进程身份推断生产服务权限也不成立。

因此本WBS不写代码、不新增冻结API、不装配default composition、不启用插件。若后续获得正式公钥/信任清单管理与部署ACL来源，按独立CR重新核查后再接入；用户持续自主授权不等于AI可替组织确立发布者身份或声称真实服务权限。

## 阻断后的执行转向

按STATUS与CR-EXEC-002，继续独立的Windows Pilot纵向交付路径，不等待上述Plugin前置。下一项先核查OUT-01-A01-P35：P34B之后是否仍缺生成文件的用户可读/下载链；先对照冻结Document/Output API、权限、Storage与TraceLink，不触碰P25 initdb诊断，也不假定下载链已通过。

