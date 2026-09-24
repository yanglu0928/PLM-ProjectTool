# 开发约束

## 任务与阶段

- 一个 WBS 任务只处理一个明确、可验证的问题。
- 不得跨 Phase 开发，不得在实现一个模块时顺手修改其他模块。
- 未完成 Phase 0 时只允许 PoC 代码；正式开发前还需依次冻结架构、核心实体/数据模型、数据库 Schema V1 和 API Contract V1。
- 已冻结事项需要变更时，单独提交 Change Request；不得混入普通实现任务。

## 数据库

每次数据库变更必须完成：ORM 修改、Alembic migration、migration review、up 测试、down 测试、空库测试、有数据升级测试。禁止手工修改生产数据库。

## API 与异常

- 冻结的 `/api/v1` 不得破坏性修改。Breaking Change 使用新 API、v2 或 API Change Request。
- 成功响应包含 `data` 与 `trace_id`；错误响应包含 `error.code`、`error.message` 与 `trace_id`。
- 错误码按 AUTH、PROJECT、FILE、AI、RAG、PLUGIN、LICENSE、REVIEW、SYSTEM 等前缀分类。
- Python traceback 不得返回前端。

## 安全底线

必须实现 Password Hash、HttpOnly Cookie、CSRF 策略、项目资源授权、文件权限检查、API Key 加密、SQL 参数化、文件类型校验、上传大小限制和审计。

License 私钥不得进入 Git、客户发行包或客户服务器，只能存在于开发者工作台。

## 文件、版本与审计

- 上传流程：临时校验 → Hash → 元数据 → 持久化 → Parser → 业务引用 → Version。
- 所有正式成果保留历史版本，禁止覆盖。
- Application、Integration、Audit 三类日志分开；Audit 写数据库，普通用户不可删除。

## 插件

插件只由开发者提供。客户可启用、禁用和安装开发者提供的独立升级包，不能安装任意第三方插件。

Manifest 至少包含 id、name、version、plugin_api_version、supported_os、supported_formats、external_dependencies、entry_point、signature。加载前检查签名、版本、兼容性、OS 和依赖。

插件不得直连数据库、管理 AI Key 或直接调用 DeepSeek；只能使用 Plugin API、AI Gateway 和 OutputContext。

## Git 与 ADR

- 分支至少包括 main、develop、feature/*、poc/*、release/*；开发代码不得直接提交 main。
- Commit 使用 feat、fix、refactor、test、docs、build、poc 前缀。
- 重要架构决策写入 `docs/architecture/adr/`，不得只保留在聊天中。
- 唯一远端仓库为 `origin = https://github.com/yanglu0928/PLM-ProjectTool.git`。
- 完成并验证的任务必须将程序、测试、文档和版本说明提交并推送到适当分支。推送前获取远端状态，禁止 force push 或覆盖未知远端修改。
- 严禁提交密码、API Key、License 私钥、客户数据、日志、临时产物或本地 Secret 配置。

## 未知项处理

信息不足时，不脑补。说明问题、影响、可选方案、建议和是否阻塞；不阻塞的部分继续，阻塞项停止。
