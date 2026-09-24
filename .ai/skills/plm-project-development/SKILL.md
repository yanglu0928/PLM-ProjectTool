---
name: plm-project-development
description: Execute architecture, PoC, implementation, testing, packaging, and deployment work for the PLM project implementation assistant while enforcing its locked V2.1 baseline, phase gates, traceability, and reporting contracts. Use for all engineering work in this repository; do not use it to reinterpret or expand the product scope.
---

# PLM Project Development

本 Skill 将《PLM项目实施辅助工具软件开发实施方案 V2.1》及用户批准的 License 专项补充 `CR-LIC-001` 作为业务与技术基线，将《AI开发总控指令与 Skill 规范 V1.1》和《AI自主执行与最小人工确认规则 V1.1》作为执行约束。2026-09-24 用户另明确授权基线不兼容时可自主记录并执行调整，最终持续推进至可用程序包。原始文档和历史冻结提交保留，差异以 Change Request 追溯。

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
- Phase 1 基础工程已完成，`1.01`～`1.09`、`PLT-01-A01～A03` PASS；Phase 2 `AUD-01-A01～A03`、`AUT-01-A01～A03`、`AUT-02-A01～A05`、`AUT-03-A01～A06`、`PRJ-01-A01～A03`、`LIC-01-A01～A04`、`LIC-02-A01～A05`、`LIC-03-A01～A03`、`PLT-02-A01～A06` PASS。用户批准 `CR-LIC-001` 方案 B 后，内部 LicenseService、验证结果/Audit 编排、受控导入/激活、运行时 Guard 与受控重验证已完成。LIC-03-A03 按用户选定方案 A 完成一次性受控初态初始化；PLT-02-A01～A06 完成 Secret 密文版本 Schema、只读信封、管理员元数据安全投影、AES-256-GCM-V1 加解密及内部创建/轮换/停用。A07 公开 API 前置核查未通过，CR-PLT-003 将生产安全装配前置；AUT-03-A01～A06 已完成可信来源、PostgreSQL 限流、真实 scrypt/Session 编排、可选 Cookie/CSRF HTTP Router、显式 SessionView 投影与本机一次性初始管理员 CLI。AUT-03-A07 生产接线按 CR-AUT-002 仍待安全运行配置；PRJ-01-A01～A03 已完成 Project 持久层、当前成员授权摘要与逐操作授权核心，下一项 `PRJ-01-A04 Project 创建命令`。首版只支持本产品全功能整体授权，生产公钥/选定 MAC/可信时间密钥来源仍未接线，Auth 默认无公开登录/管理 API；Gate 3 尚未通过。
- 冻结后的总体架构、核心数据模型、DB Schema V1、Breaking API、技术栈、安全/License 机制或 Scope 变化须先建立 Change Request，记录影响与验证后依 V1.1 持续授权执行，不得静默改写。
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

用户 2026-09-24 已明确授权原方案不兼容时可自主选择并执行解决方案。发现问题先记录风险、证据、方案比较、所选方案、迁移/回滚与验证到 Change Request；保留原基线历史，再实施并同步 GitHub。不得由默认授权推定测试/Gate 已通过。

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
- L1 工作自主完成；L2 决策记录到 `docs/decisions/decision-log.md` 后继续；原 L3 事件按 V1.1 建立正式 Change Request 后自主执行。真实环境/数据或付款等无法由 AI 代替时记录客观限制并继续不受阻塞的任务。
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
