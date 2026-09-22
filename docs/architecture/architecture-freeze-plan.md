# Architecture Freeze 执行计划

## 状态

`IN_PROGRESS / AF-01_PASS / AF-02_PASS / AF-03_PASS / AF-04_NEXT`

## 前置 Gate

- Phase 0 Gate 1：`APPROVED`（2026-09-22）。
- 阶段结论：`COMPLETE_WITH_APPROVED_ALTERNATIVES`。
- 约束：Gate 2 前只允许架构、数据模型、Schema、API Contract、ADR、验证脚手架与基础空壳设计；禁止正式业务功能编码。

## 输入基线

1. 《PLM项目实施辅助工具软件开发实施方案 V2.1》。
2. 《AI开发总控指令与 Skill 规范 V1.1》。
3. [Phase 0 总结](../progress/phase-0-summary.md)。
4. [Phase 0 验证例外](../poc/phase-0-exceptions.md)。
5. 已接受 ADR-001、ADR-002 与 Phase 0 各 PoC 证据。

## 不可改变的架构约束

- 模块化单体、单服务器部署；第一版不拆微服务。
- 依赖方向：`UI → API → Application Service → Domain → Repository / Gateway`。
- 模块间只通过 Application Interface、Domain Event、TraceLink 和 DTO/Contract 通信。
- AI、Retrieval、Plugin、Trace、Review 必须使用统一服务入口。
- PostgreSQL 18 + pgvector；文件内容保存在本地文件系统，数据库保存元数据。
- PROJECT 知识必须按 ProjectId 隔离；Embedding 模型变化必须新索引、全量重建。
- Plugin 为独立 Python 子进程 + JSON-RPC over stdio；不得直连数据库或管理 AI Key。
- License 为显式 MAC 选择 → Normalize → SHA-256 → Ed25519；私钥只存在开发者工作台。
- AI 输出只允许作为建议；人工确认后才能成为正式业务事实。

## AF-01～AF-05

|WBS|目标|交付物|完成判定|
|---|---|---|---|
|AF-01|收敛模块与上下文边界|模块目录、职责、Owner、允许依赖、禁止依赖|PASS；见 `module-boundaries-v1-candidate.md`|
|AF-02|冻结统一服务与跨模块通信|AIService、RetrievalService、PluginService、TraceService、ReviewService 端口及 Domain Event 清单|PASS；见 `application-contracts-v1-candidate.md`|
|AF-03|冻结安全、文件、任务与运行边界|认证/授权链、文件流、日志、Job Worker、配置和 Secret 边界|PASS；见 `security-file-job-runtime-boundaries-v1-candidate.md`|
|AF-04|补齐关键 ADR|模块化单体、AI/RAG、Plugin、License、Job、文件存储、质量替代控制 ADR|每个长期决策具备 Context/Decision/Consequences/Rollback|
|AF-05|生成 Architecture Freeze 候选|架构总览、依赖矩阵、运行视图、部署视图、风险与例外清单|无未登记架构分歧，进入 Data Model Freeze|

## 后续冻结顺序

```text
Architecture Freeze Candidate
→ Core Entity / Data Model Freeze
→ Database Schema V1
→ API Contract V1
→ Gate 2
→ Phase 1 基础工程与正式编码
```

## Phase 0 遗留约束映射

|来源|Architecture Freeze 处理|
|---|---|
|POC-03 分类/引用 FAIL|AI 结果始终建议态；ReviewService 强制人工确认；质量指标作为 Gate 3/UAT 阻塞|
|POC-06 Server Office 未验证|Office 不是服务器依赖；输出 Contract 只保证标准 OOXML，Release 仍需客户端 Office 回归|
|Debian 13 暂缓|保留 Linux 路径、进程、文件权限和打包抽象；不得写入“已验证兼容”|
|Ghostscript AGPL|发行前公开源码、许可证与对应源代码成为 Release Gate；当前私有开发仓库不等于合规完成|
|Plugin 短命子进程 PoC|正式设计可定义生命周期管理，但不得改变 stdio/独立进程基线而无 Change Request|
|License 时钟状态|Architecture Freeze 明确可信时间状态存储端口；不得把私钥带入客户侧|

## 当前不做

- 不创建正式业务数据库表或 Alembic migration。
- 不冻结 `/api/v1` 具体端点。
- 不实现 UI、业务 Service、Repository 或正式 Worker。
- 不引入 Redis、消息队列、独立向量库、本地模型、SSO、容器化插件或第三方插件市场。

## 下一输出

AF-04 关键 ADR；完成后进入 AF-05 Architecture Freeze Candidate，不请求普通人工确认。只有改变锁定技术栈、总体架构或出现不可裁决长期方案时触发 L3。
