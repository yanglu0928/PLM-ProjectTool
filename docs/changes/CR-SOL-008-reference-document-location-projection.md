# CR-SOL-008：PROJECT Reference 固定文档来源的可定位身份投影

日期：2026-10-09；状态：按 `CR-EXEC-001` 持续授权先登记，后端投影已实施并验证；前端入口待接线。原 Gate 2 冻结 API-04 及提交 `64cdf09` 保留不追写。TraceLink：冻结 `SOL_REFERENCE_GET` → P04-P01/P02 当前版本固定来源读取 → 本 CR → SOL-01-A04-P07 前端定位。

## 冲突与证据

冻结 API-04 要求 Reference GET 返回固定 reference/source refs，用户要求在界面点击后快速定位原文。当前已实现 GET 只返回 `document_version_ids[]` 和 `evidence_ids[]`；现有 Document 详情与固定版本内容路径必须同时知道 `document_id` 和 `document_version_id`。Evidence 有独立受权 Viewer 可按 EvidenceId 定位，但裸 DocumentVersionId 在现有公开 API 中无法直接得到根 DocumentId。让前端逐页扫描文档或猜测根身份会遗漏、超时，并可能错误关联来源。

## 方案比较与选择

- 不选前端扫描所有项目文档与版本：数量无上界、响应不稳定，且无法保证固定版本当前可访问。
- 不选新建无鉴权的全局 VersionId 反查 API：扩大数据可见面，破坏项目隔离。
- 选择对已受权 PROJECT Reference GET 兼容增加有序 `document_refs[]`，每项只含同项目固定 `document_id` 与 `document_version_id`。保留原 `document_version_ids[]` 不变并要求两数组一一相符。由服务端同一读取事务验证版本归属，客户端只构造现有受权 Document 详情链接；实际原文访问仍由 Document/Evidence 端点重新检查 Session、Project、License、文件完整性。EvidenceId 仍通过现有 Viewer 取得精确定位，不增加裸路径。

## 差异、风险、迁移/回滚与验证计划

相对既有 GET 增量合同是响应只读字段的兼容补充，不改变 URL、Method、旧字段、状态码、权限或冻结 `/api/v1` 行为；不含正文/绝对路径/客户 Secret。无 ORM/Schema/Migration/依赖变化，历史行无需迁移。风险：错配/跨项目 DocumentId 或客户端把链接当来源有效证明；服务端必须按序核对版本/根/Scope/ProjectId，异常失败关闭，前端展示“历史固定来源、点击时重新验证”，不可自动声明可用。回滚可关闭新增投影与对应 UI 入口；已存历史不变，原字段保留。

验证计划：单元覆盖顺序/数量/重复/错配、API 响应白名单、隔离 PG18.6 真实 DocumentVersion 归属与跨项目/异常负例、现有 GET/List/创建回归、前端严格响应解析和只使用同项目固定链接；全量后端/前端测试与版本说明同步。正式 License、目标服务账户、Server 2025、Debian13、浏览器 UAT、Gate3/发行仍按客观证据关闭。
