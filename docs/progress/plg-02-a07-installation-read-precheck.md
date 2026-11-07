# PLG-02-A07：PluginInstallation只读详情API编码前检查

- 日期：2026-11-04
- 状态：`PASS_SCOPE_LIMITED`（实现及托管验收完成）
- WBS：PLG-02-A07
- 变更记录：`docs/changes/CR-PLG-012-plugin-installation-read-api.md`
- 前置：PLG-02-A01～A06均为`PASS_SCOPE_LIMITED`

## 冻结契约与现状

API-03冻结了`PLUGIN_INSTALLATION_GET`：GET `/api/v1/admin/plugins/installations/{installation_id}`，DeploymentAdmin，只读Session与有效License，返回运行时兼容/启用操作以及ETag。当前Plugin API只有package import；没有Installation metadata GET Service、Query Repository或Router。现有`SqlAlchemyPluginInstallationRepository`仅支持受控写入/安装事实Owner，不提供只读投影。

Schema V1已有Installation、Verified Package、Manifest Operation、RuntimeValidation和EnabledOperation事实，能支撑单条详情读取，无需迁移。生产入口已有真实Session、DeploymentAdmin read access和License guard装配；Production平台Read/Write模式在信任条件可用时挂载读取面。不得把不存在的真实宿主安装事实伪造成可用数据。

## 本项范围

按`CR-PLG-012`只实现单条Installation安全读取链：内部查询DTO/只读应用服务、SQLAlchemy只读查询Repository、冻结`PLUGIN_INSTALLATION_GET`HTTP Router及契约/PG测试。明确排除list分页、安装/复验/启用/停用/退役HTTP写路由、默认应用装配和真实文件安装器。

只返回固定白名单字段：installation/package/plugin identity、package hash/manifest允许操作摘要、installation state、runtime compatibility与精简runtime snapshot、enabled operations、lock_version/ETag。不得暴露Package正文、签名私钥/原始签名、路径、环境变量、PID、stdio、traceback、Secret或ORM对象。

HTTP按现有只读边界校验trusted host与Session，不要求CSRF；应用服务在查询前后重新核验DeploymentAdmin会话，执行License Guard；不存在或无权资源统一返回RESOURCE_NOT_FOUND。详情无query参数，响应Cache-Control no-store及`ETag: "v<lock_version>"`。

## 验收与限制

- 使用合成管理员Session、合成License Guard与临时PG18，验证Installed/Enabled/Disabled/Retired读取、操作列表、runtime投影、精确ETag、跨权限/过期Session/无License/不存在对象失败关闭；读取不得写Audit/业务数据。
- 后端定向与全量测试、wheel；PG18真实SQL与response contract。Hosted D盘临时工作区；不在本机/C盘执行。
- 只在显式Production Platform Read/Write组合中挂载；默认应用继续无此路由。正式License信任未供给时，应用启动失败关闭，合成测试不能代表产品运行。
- 最高为`PASS_SCOPE_LIMITED`，不等于真实安装适配器、Win11实机、Pilot、Gate或Release通过。


实现结果：`docs/progress/plg-02-a07-installation-read-result.md`。