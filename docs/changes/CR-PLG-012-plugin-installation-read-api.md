# CR-PLG-012：PluginInstallation只读详情API

- 日期：2026-11-04
- 状态：已登记；PLG-02-A07编码及托管验收待完成
- WBS：PLG-02-A07
- 基线：Gate 2冻结Data Model V1、DB Schema V1、API Contract V1；CR-PLG-007～011

## 原因和决定

冻结API-03定义`PLUGIN_INSTALLATION_GET`，但Plugin模块尚无Installation读取Service/Repository/HTTP API。后续管理员停用操作需先取得当前lock_version和安全状态。现有表/字段已足够；本项只新增只读投影，不改Schema或API合同。

新增单Installation metadata读取Service、SQLAlchemy Repository与HTTP Router。复用DeploymentAdmin真实只读身份查询和License Guard。响应投影固定为PluginInstallationView白名单，仅呈现包/安装身份、包Hash、允许操作、当前安装/runtime验证状态、精简RuntimeSnapshot、当前EnabledOperation及`"v<lock_version>"` ETag。Session与License于读取前后重新核验；GET不要求CSRF，不写Audit/业务状态；不存在/越权统一资源不可见。

## 风险和回滚

风险为敏感Manifest/宿主信息过度暴露、绕过管理员/License检查及读取过程中状态混合。逐字段投影、只读事务/单条快照、会话再验证、无Store变更测试、ETag版本及安全投影审查缓解。回滚删除新增读取入口/模块，不需迁移；不会改动已有Installation数据。

真实宿主安装、公钥/License正式信任仍未具备；HTTP只读取数据库已有事实，不创建安装、不连接文件系统或执行插件。只在明确的Production Platform Read/Write组合中挂载，默认模式仍404。


## 编码阶段静态复核记录（2026-11-04）

- 单元测试初稿对License模拟异常的预期错误码写成`SYSTEM_UNAVAILABLE`，与当前Service的稳定内部错误映射`PLUGIN_INSTALLATION_UNAVAILABLE`不一致。
- 发现于云端执行前；尚无A07测试验收结果，产品逻辑与API错误合同没有修改。
- 处理计划：只修正测试断言以匹配Service稳定错误映射，再交由GitHub hosted全量测试确认。


## 国际化显示名兼容复核记录（2026-11-04）

- Manifest Parser按冻结包合同允许UTF-8插件显示名称，只拒绝控制字符；A07只读Repository初稿另加ASCII字符白名单，会导致合法中文显示名称无法读取。
- 发现于托管执行前，不是既有数据/生产安装事实，也未运行含中文数据。
- 处理计划：保持1～255字符与拒绝控制字符的规则，移除只读投影新增的ASCII限制；同时保留对版本、运行时、包Hash和可枚举状态的严格验证。使用合成中文名称单测及PG18详情读取覆盖。


## 首次托管全量验收偏差（2026-11-04）

- GitHub hosted run `41759144508` 后端全量测试在 `test_optional_plugin_installation_read_router_is_mounted_only_when_supplied` 失败；3967项中该1项报错。
- 原因是测试用例直接读取 `app.routes[*].path`；当前FastAPI版本将包含的路由以内部 `_IncludedRouter` 包装对象暴露，该对象没有公开 `path` 属性。A07业务测试的前置预检及前端测试/构建成功；因后端失败，依赖作业跳过，不能视为A07通过。
- 影响范围限于路由挂载断言测试，不是产品路由逻辑或API行为失败。
- 修复计划：断言FastAPI公开生成的OpenAPI路径集合包含显式提供的路由、且默认工厂路径集合不包含它；不改变工厂或生产装配。随后重新执行GitHub hosted全量验证，保留失败run链接和新run结果。
