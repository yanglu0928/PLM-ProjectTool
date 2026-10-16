# AI-04-A06-P03-P02-A03 Document 精确解析内容 Owner

日期：2026-10-03；状态：`PASS`；依据 CR-AI-015/016、DEC-726～729。无 Schema、公开 API、依赖、Provider 调用或客户数据外发。

## 实现

- 为 Content Plan 补齐无正文 `AIExecutionContentReadQuery`、短生命周期 `AIExecutionContentProjection` 和读取 Owner Port；正文 bytes、源/结果摘要及 locator 均不进入 repr。
- 新增 Document-owned `DocumentAIContentService`。规划阶段在调用方事务内按 `completed_at DESC, parse_record_id DESC` 确定一个成功解析结果；执行阶段只按冻结的 DocumentVersion、ParseRecord、ParseResultRef、parser 版本及两个 SHA-256 精确读取，不重新选择“最新”。
- 新增 PostgreSQL Owner Repository，以共享锁同时复核 Document、DocumentVersion、FileObject、ParseRecord、ParseResultRef 的 PROJECT 归属、可用状态、文件元数据、成功状态、结果引用/hash 和 schema；不向 AI 暴露存储 locator。
- 增加内部 Project 操作 `AI_TASK_EXECUTE`，仅 ProjectManager/ImplementationMember 可执行且按写语义锁定当前成员、部门和项目事实。后台 Worker 不复用浏览器 Session，而以 Task 冻结的原请求人身份在每次规划/读取时重验当前权限；归档项目、暂停/移除成员失败关闭。
- `minimum.document.text.v1` 只投影规范化的 node id/kind/text，移除 source locator、OCR confidence 和原始解析元数据；要求 parser 发布 JSON 为唯一 key、有限数、规范 UTF-8 JSON，正文统一 NFC/LF，拒绝不支持的 node kind、控制字符、空正文、越限及文件/数据库漂移。
- 新增 `AIDocumentContentOwner` 反腐层，把 DOC-02 / `document/DOCUMENT_VERSION` 映射为无 locator 的通用 Content Plan 身份；Document 错误统一收敛为 AI source unavailable。

## 验证

- 定向 19 项 PASS，覆盖固定结果不漂移、执行期重新鉴权、hash/数据库漂移、非规范 JSON、错误 node kind、控制字符、空正文、最小投影和 repr 隔离。
- Windows 11 / PostgreSQL 18.6 / 本地私有结果文件真实链：先规划并冻结第一条 ParseRecord，再插入完成时间更晚的第二条；旧 Plan 仍逐字节读取第一条，新规划确定第二条；暂停原请求人和篡改第一条结果文件均拒绝。Invocation 数为0，无 Provider 调用。标记：`AI_04_A06_P03_P02_A03_DOCUMENT_CONTENT_PG_PASS`。
- 后端全量：`Ran 2185 tests in 38.118s`，`OK (skipped=3)`。
- 开发 wheel SHA-256：`5bed8f10c02b9935de2224a227d68f3d410dbde1306b78293450d7ec9252800d`。

## 偏差、兼容与回滚

编码前发现既有 Document 读取依赖浏览器 Session，不能作为后台 Worker 的当前权限证明；按持续授权采用独立内部 `AI_TASK_EXECUTE` 策略和原请求人当前 Project 权限复核，登记 DEC-729。该调整不改变冻结公开 API、角色集合或业务数据，只明确后台执行门禁。通用 Owner 方法名在首轮运行前与既有 Port 的 `resolve_identity` 对齐；未产生失败验证或数据影响。

本项复用 Schema0071 与现有 Document/Project 表，无 Migration、公开路由、生产 Worker 装配或网络 I/O。回滚可撤新 Owner/Repository/反腐层和内部策略项；现有文档、解析结果、Task 与授权历史不变。旧无 Content Plan 记录仍不可执行。Windows Server 2025 尚未在本项复验；Debian 13 按用户指令跳过，不能据 Win11 结果宣称已验证。

下一任务：`AI-04-A06-P03-P02-A04`，实现 provider-neutral Envelope 规范编码、Context policy 失败关闭和可注入版本化 Token estimator，不执行网络 I/O。

后续 A04 在持久化前补强通用身份：新增最小正文 `projection_fingerprint`，Document Owner 规划时计算、执行时重算。该字段与 ParseResult 原始 hash 并列，详情见 DEC-730/A04 进度，不改变本项 PG/权限/存储结论。
