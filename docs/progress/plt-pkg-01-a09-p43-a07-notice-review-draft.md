# PLT-PKG-01-A09-P43-A07：第三方通知审阅草案

日期：2026-10-01；状态：`NOTICE_DRAFT_INPUTS_VERIFIED / FORMAL_NOTICE_BLOCKED`。输入 P43-A03 固定候选、P43-A06 第三方证据差异、34 项原生 PE 矩阵及 Artifex 官方许可说明。输出 [第三方通知审阅草案](../release/THIRD-PARTY-NOTICE-REVIEW-DRAFT.md)；它不进入候选包，也不是最终产品 `NOTICE`。

编码前检查：当前 Phase 2/Gate 3 未关闭。本任务只汇总可核实的发行证据供负责人和合格法律审阅人员使用，无实体/API/权限/Schema/Migration/SCM/正式安装变化。验收要求先重验固定 P43/P33/P22 谱系和原生矩阵，再分清自有与第三方分发包、缺少的许可表达式/通知文件，草案显式标记不可发行；风险是把原始元数据、供应商说明或“源码已在包内”扩大解释为最终法律结论。

新增只读工具 `tools/audit_notice_draft_inputs.py`，真实固定包审计退出 0、定向单元 3/3。106 个 Python 分发包中 1 个为自有后端、105 个为第三方；60 个第三方包的 `license_expression` 为空。三项无嵌入式通知：`bce-python-sdk`、`et_xmlfile`、`openpyxl`；后两项有独立 wheel 侧载，只有 `bce-python-sdk` 在该候选中既无嵌入式又无独立通知材料。P43-A06 曾用“Python 库 106 个”的概括，现更正为“Python 分发包 106 个，含自有后端 1 个”，不追改历史证据。

草案按 Ghostscript、Caddy/Go、PostgreSQL/pgvector、Python、前端、原生 OCR/模型分组，给出已存在的证据与待审事项；没有编造版权归属、替用户选择产品许可证或把外部官方许可说明当成项目法律签核。产品根目录 `LICENSE`/`NOTICE` 与固定候选内产品级文件仍不存在。兼容性：只新增审阅材料及只读工具，无运行或发行候选变更；升级无迁移。`release_eligible=false`。下一项应依据草案处理可由技术核实的精确发行许可材料缺口，法律适用及最终对外许可仍须合格复核；并继续正式信任源、目标平台和 Gate 的独立任务。
