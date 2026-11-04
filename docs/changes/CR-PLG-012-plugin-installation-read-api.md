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
