# TRC-01-A06-P03-P03：DOC-02 三字段引用真实 Scope 解析

日期：2026-10-02；Phase 2；状态：**内部DOC-02 Owner PASS，通用图HTTP未开放**。输入冻结 API-02 三字段`ResourceVersionRef`、Document 事务内固定版本证明、CR-TRC-002 与决策 `DEC-20261002-612`；Gate 2 原冻结提交 `64cdf09` 保留。

Document 自有 Repository 以 DocumentId+VersionId 在调用方事务中共享锁定位真实 Scope/Project；PROJECT 必须与路径 ProjectId 相等，GLOBAL 仍要求 Document 原有 DeploymentAdmin 当前 Session 权限。随后在同一事务复用现有 License、Document/Version/File 可用性与授权证明，组合层才构造完整内部 TraceVersionRef。未注册类型、无权、错项目、缺版本或受限文件失败关闭；身份预读结果不单独对外投影，不从路径猜 Scope。

验证：新单元6项（Document解析4、Trace Owner桥接2）；隔离 PostgreSQL 18 自启动脚本扩展实际PROJECT/GLOBAL、当前用户权限、跨项目、缺版本、File受限与过期License拒绝，并回归Trace创建/重放/Audit/图页；退出0且临时库/进程清理。后端全量1885运行/3跳过/无失败；开发wheel SHA-256 `84a2bbcf14532c70d15ac4d28dd321cec8b6775d97a8e783399cb6a8bc32ec9b`。

兼容/升级/回滚：仅Document内部只读Port、Trace三字段DTO/组合桥接、测试；无公开API、Schema/Migration、新依赖或历史数据改写。未装配该解析入口即可回滚。其他业务Owner仍未解析；正式目标账户Trace游标密钥、公开图HTTP、Server2025/Debian、性能、正式License/法律、UAT/Gate与可用发行包未因此通过。
