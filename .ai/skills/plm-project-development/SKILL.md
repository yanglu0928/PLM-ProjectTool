---
name: plm-project-development
description: Execute architecture, PoC, implementation, testing, packaging, and deployment work for the PLM project implementation assistant while enforcing its locked V2.1 baseline, phase gates, traceability, and reporting contracts. Use for all engineering work in this repository; do not use it to reinterpret or expand the product scope.
---

# PLM Project Development

本 Skill 将《PLM项目实施辅助工具软件开发实施方案 V2.1》作为最高业务与技术基线，将《AI开发总控指令与 Skill 规范 V1.1》和《AI自主执行与最小人工确认规则 V1.0》作为执行约束。原始文档始终是事实来源；本 Skill 只负责路由和执行，不替代原文。

## 开始任务

1. 新 Session 先读取根目录 `.ai/SKILL.md`、`STATUS.md` 和自主执行规则。
2. 识别当前 Phase、WBS、前置条件、输入基线及验收标准。
3. 不自动检查 Codex/GPT 周额度；只有用户明确要求时才读取，且不得未经逐次确认使用额度重置或购买。
4. 检查 `docs/architecture/adr/`、冻结数据模型、冻结 API Contract 和相关模块文档是否存在。
5. 读取下方与任务相关的参考文件；只在基线相关、Gate、L3 或版本变化时重读完整基线。
6. 若前置 Gate 未通过，不进入后续阶段；完成仍被允许的验证或文档工作。

## 当前项目状态

- Phase 0 Gate 1 已通过，结论为 `COMPLETE_WITH_APPROVED_ALTERNATIVES`。
- Gate 2 已于 2026-09-23 由用户明确批准；Architecture、Data Model、DB Schema V1 和 API Contract V1 已按提交 `64cdf09` 冻结。
- 当前处于 Phase 1 架构冻结与基础工程；`1.01`～`1.09` 的基础任务已 PASS，下一任务为 `PLT-01-A01 SystemConfiguration ORM/Migration`；正式实现必须按 WBS、编码前检查和冻结基线推进。WBS 1.09 只完成 Config/Secret 边界，不代表生产密文仓库或主密钥保护已实现。
- 冻结后的总体架构、核心数据模型、DB Schema V1、Breaking API、技术栈、安全/License 机制或 Scope 变化属于 L3，不得由实现任务自行修改。
- POC-03 质量失败继续阻塞 Gate 3/UAT；Server Office、Debian 13 和 Ghostscript 发行合规继续由各自 Release Gate 关闭。

## 参考文件路由

- 涉及模块边界、依赖、AI/RAG、Trace、Review 或数据流时，读取 [architecture.md](references/architecture.md)。
- 涉及语言、框架、数据库、文档处理、插件、License 或部署平台选型时，读取 [technology-baseline.md](references/technology-baseline.md)。
- 涉及编码、数据库/API 变更、版本、异常、安全、Git 或 ADR 时，读取 [development-rules.md](references/development-rules.md)。
- 涉及测试设计、验收、Definition of Done 或质量 Gate 时，读取 [testing-rules.md](references/testing-rules.md)。
- 涉及 Phase 0 或任何技术可行性结论时，读取 [poc-rules.md](references/poc-rules.md)。
- 涉及安装、升级、打包、交付、三平台或 Release Gate 时，读取 [release-rules.md](references/release-rules.md)。

## 决策规则

优先级：用户最新明确变更 > 正式锁定方案 > 已冻结 ADR > 已冻结数据模型/API Contract > 当前阶段设计 > AI 建议。

只有用户明确表示“修改已锁定方案”时，才能修改正式基线。发现问题时，输出风险、证据、影响和变更建议，等待确认；不得自行替换技术或业务规则。

不要把“合理推断”“待验证”或 AI 生成内容写成“已验证”。技术可行性只有在对应 PoC 具备完整记录并 PASS 后才能确认。

## 编码前检查

任何正式编码前，先输出并确认：

```text
当前Phase：
当前WBS：
输入基线：
前置任务：
涉及模块：
涉及实体：
涉及API：
涉及权限：
验收标准：
风险：
```

前置未完成时停止该任务，不以临时代码绕过 Gate。

## 执行边界

- 一个任务只解决一个可验收问题；把“开发某模块”拆成实体、接口、权限、版本和测试等独立任务。
- 不跨 Phase，不跨层顺手实现，不擅自扩大 P0 Scope。
- 保持 UI → API → Application Service → Domain → Repository/Gateway 的依赖方向。
- 正式业务事实必须来自结构化对象和人工确认；AI 输出只是建议。
- 正式 Requirement、Prototype、Solution Section、WBS Task 必须具有可反向查询的 TraceLink。
- L1 工作自主完成；L2 决策记录到 `docs/decisions/decision-log.md` 后继续；L3 事件停止受影响任务并请求用户决策。
- 每个 WBS 完成后更新根目录 `STATUS.md`，满足自动继续条件时直接进入下一 WBS。
- 当前批准 Scope 内可自主提交并推送到正确 Git 分支；仍须遵守远端同步和 Secret 检查规则。

## 默认响应合同

开发执行型任务默认使用：

```text
【当前阶段】
【当前任务】
【基线检查】PASS / BLOCKED
【本次目标】
【输入】
【实施步骤】
【预计修改文件】
【验收标准】
【风险】
【执行结果】
【测试结果】
【遗留问题】
【下一任务】
```

完成一个任务后，必须明确 Changed、Files、Migration、API、Tests、Result、Known Issues、Next。若用户只要求简短状态，可压缩篇幅，但不得省略阻塞、失败或未验证事实。
