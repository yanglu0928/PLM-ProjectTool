# PLT-PKG-01-A09-P43-A06：新候选第三方发行证据差异清单

日期：2026-10-01；状态：`GHOSTSCRIPT_SOURCE_ADDED_LEGAL_REVIEW_OPEN / RELEASE_BLOCKED`。固定 P43-A03 新候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P33/P22 谱系及 34 项原生 PE 发行义务矩阵 SHA-256 `a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc`。

编码前检查：Phase 2/Gate 3 开放；本项只做固定包与已跟踪矩阵的只读证据分类，不修改产品、API、Schema、权限、SCM、安装根或客户资料。验收为先全量验 P43/P33/P22 谱系与矩阵 Hash，再核关键路径/数量/嵌套 `REVIEW_REQUIRED` 状态，不能把许可文本或源码文件的“存在”解释为法律义务完成。风险是文件数量掩盖单个组件义务或元数据误标发行可用。

真实工具 `tools/audit_ghostscript_source_release_gaps.py` 退出 0、定向单元 3/3。固定候选含 3 份源码归档（Caddy、Go 标准库、Ghostscript），第三方证据目录 190 份文件（含 LICENSE、NOTICE、SBOM 和校验文本，并非 190 份已批准许可证）；产品级 `LICENSE`/`NOTICE` 为 0。Python 库 106 个，历史独立许可/通知文件 152 份，新增 OCR Python 侧载通知 25 份；前端独立许可侧载 6 份但前端复核仍为 `REVIEW_REQUIRED`。Caddy SBOM 149 组件，下游通知复核为 false；PostgreSQL/pgvector 审核为 `REVIEW_REQUIRED`；34 项原生 PE 的 `release_obligations_reviewed` 均为 `NO`；Ghostscript 源码已随包，但其法律复核仍为 `REVIEW_REQUIRED`、`legal_clearance=false`。

需要的后续工作：确定并经合格复核产品级发行许可与组合分发方式；逐组件完成 34 项原生 PE、106 个 Python 分发包、前端/Caddy/PG/pgvector/模型/Ghostscript 的精确 NOTICE、来源及对应源码义务；形成可供发行的产品 LICENSE/NOTICE，再做独立法律签核。Artifex 的[许可说明](https://artifex.com/licensing)将 Ghostscript 列为 AGPL/商业双许可并强调其所述服务/集成场景的源码披露要求；这仅是供应商公开说明，AI 不据此作本产品法律结论。用户计划公开 GitHub 源码，也不能单凭此事实把完整发行义务标记为满足。

兼容性：只新增只读审计工具和报告，无包/API/Schema/SCM变化。升级：无迁移。回滚：弃用审计报告，不影响固定候选；但缺口客观存在。`release_eligible=false`。下一项准备由已有逐组件证据生成可供合格复核的产品级 NOTICE 草案，草案不能替代正式法律批准；正式账户/证书/License、目标平台、Gate/UAT仍独立阻断。
