# LIC-03-A03 编码前检查：生产可信来源与初始化装配

- 日期：2026-09-24；结果：DECISION_REQUIRED；未修改程序、Schema 或 API，未宣称任务 PASS。
- 当前 Phase：Phase 2。前置：LIC-03-A01/A02、LIC-02-A02～A05 已完成内部端口与验证；生产信任源未装配。
- 证据：`STATUS.md` 上的 LIC-03-A03 仅是上轮暂定任务，未列批准验收标准。Gate 2 冻结架构 `architecture-freeze-candidate-v1.md` 的 R-AF-003 与第 319 行将 SecretKeyProvider 平台实现和密钥恢复留给 Release 安全设计；`security-file-job-runtime-boundaries-v1-candidate.md` 要求密文/主材料分离，Windows/Linux 保护实现进入 Release 安全设计。`DEC-20260924-068`、`wbs-1.09-config-secret-report.md` 明确当前 SecretResolver 仅为访问边界，不是生产 Secret Store。`DEC-20260924-087` 明确 TrustedTime HMAC 密钥由独立受信任解析器提供、缺失时失败关闭，首次空状态由部署装配显式创建。
- 影响：直接选定环境变量、YAML、普通文件或未经批准的 OS 密钥方案，会把未验证的保护/恢复机制误称为生产能力，并越过冻结架构的 Release 安全设计边界。缺失密钥来源时无法验收生产可信时间装配或开放 License 业务。
- 方案 A（建议）：保持既定 Release 安全设计时点；将 LIC-03-A03 缩为一次性受控初态初始化（不接生产密钥），生产 SecretKeyProvider、密钥恢复和完整装配进入后续 PLT-02/Release WBS。不能把此子任务标为生产可信来源 PASS。
- 方案 B：明确批准现在提前开展跨平台 SecretKeyProvider、备份/恢复与失密失败关闭设计及验证，再实施完整 LIC-03-A03；这改变冻结架构安排的阶段边界，需单独记录 L3 Change Request。
- 未处理后果：继续失败关闭；没有生产 License 授权放行。可继续与该密钥选型无关的独立 WBS，但不得宣称 Gate 3/Release 通过。
- 用户结论：2026-09-24 明确选择方案 A；本项改为一次性受控初态初始化，生产密钥来源/恢复仍留待 PLT-02/Release。持续执行授权及差异追溯见 `docs/changes/CR-EXEC-001-continuous-delivery.md`。
- 处置：受控初态初始化已作为缩小后的 LIC-03-A03 实现与验证，结果见 `docs/progress/lic-03-a03-initialization.md`；原 DECISION_REQUIRED 为历史状态，当前无待用户决策。
