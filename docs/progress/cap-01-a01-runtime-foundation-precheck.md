# CAP-01-A01：GLOBAL Capability 最小真实 Owner 前置核查

日期：2026-10-05。结论：`CAP_01_A01_PRECHECK_PASS`。下一项：`CAP-01-A02` Schema0091/ORM。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；依据CR-SEQ-001前置Phase 4所需最小真实Owner
当前WBS：CAP-01-A01
输入基线：Gate 2冻结DM-05、SC-01/02/04、API-04、ADR-009、CR-SEQ-001
前置任务：GATE-3-A01审计完成；Document/Evidence/Review/Audit基础机制存在
涉及模块：新增capability；依赖document、evidence、review、trace、audit，不反向写其表
涉及实体：CAP-01 CapabilityBaseline、CAP-02 BaselineVersion、CapabilityItem及固定引用
涉及API：本项不实现；后续保持API-04十二个Capability Operation不变
涉及权限：GLOBAL写仅DeploymentAdmin；项目成员只能读取被正式项目引用且策略允许的APPROVED版本
验收标准：识别当前实现差距，固定最小物理化、Owner边界、迁移/回滚与验证顺序
风险：把本地标准资料、AI建议或Draft误当正式能力；来源集合引用悬空；Review跨Owner写表
```

## 核查结果

1. 当前 `apps/backend` 没有 capability 模块、ORM、Migration、Repository、Service 或 Router；数据库迁移头为 `20261004_0090`。
2. 冻结 Schema 明确两 Root/五表：`cap_baselines`、`cap_baseline_versions`、`cap_items`、`cap_item_evidence_refs`、`cap_item_document_refs`；SC-04 与 Audit 白名单已有 CAP-01/CAP-02，占位合同不是运行实现。
3. API-04 冻结十二个 Capability Operation；本阶段先建 Schema/内部 Owner，再接 Review，最后开放默认关闭 Router 和 Windows 显式生产组合，避免半成品 API 暴露。
4. Capability 是 Handover 的强制正式输入，也是 Review/Trace/Workflow 回接的第一个真实业务 Owner；因此该前置顺序符合 `CR-SEQ-001`，但不表示 Phase 4 已开始验收或 Gate 3 已通过。
5. `source_collection_ref` 缺物理 Owner/表。已建立 `CR-CAP-001`，选择由精确 GLOBAL DocumentVersion 集合产生不可变 `sha256:` 引用，不新增 Root、不借用 RAG Index、不接受 opaque 悬空引用。

## 最小运行边界

- Baseline Identity 仅保存 GLOBAL 元数据、受控来源集合引用、状态、正式指针与乐观锁。
- BaselineVersion/Item/文档/证据集合创建后不可变；状态变化只能由后续唯一 Owner 执行。
- A02 只允许无正式指针的结构化历史存在，不开放 APPROVED、Review 或 HTTP 状态转换。
- A03 通过 Document/Evidence 的公开 Owner Port 重验固定 GLOBAL 来源，不直查其他模块内部表。
- A04 通过 Review Port 创建/消费固定主题；ReviewService 不直接写 Capability 表。
- AI 只可形成 Suggestion/Draft 输入，不能更新正式指针；现有标准能力库资料不自动导入。

## 验证与兼容

本项为静态核查，无代码、Schema、Migration、API、依赖、网络或客户数据外发。已核对冻结 DM/API/SC、运行源码、迁移头、Audit 白名单及 SC-04 manifest。回滚为停止后续任务并保留本记录；`CR-CAP-001` 实施前无数据迁移。Gate 3继续保持`BLOCKED`。
