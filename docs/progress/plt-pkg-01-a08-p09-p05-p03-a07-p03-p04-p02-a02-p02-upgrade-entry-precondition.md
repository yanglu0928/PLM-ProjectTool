# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A02-P02：正式升级入口前置核查

日期：2026-10-01；状态：`PRECONDITION_BLOCKED / INDEPENDENT_PACKAGE_WORK_CONTINUES`。

当前 Phase/WBS：Phase 2 / 本项。输入为 CR-PKG-004、P04-P02-A01 合成恢复、P04-P02-A02-P01 连续维护锁、Release 固定流程与 PLT-MAINT-01 静止清单。涉及升级工具和 Windows 部署环境；不修改实体、API、Schema、权限或生产数据。验收须在正式目标账户与安装目录下核查人工备份/恢复、维护态、三项服务及旧版/未知进程和 DB/文件 I/O 静止，并保持同一排他锁直到复制/Migration 的关键步骤结束；任何证据缺失应拒绝升级而非用人工布尔值代替。

本机只读核查：`C:\PLMTool` 不存在；固定的 `PLMProjectToolApi`、`PLMProjectToolAuditWorker`、`PLMProjectToolParserWorker` 均未安装。现有 `process_inventory_windows`、`process_identity_inventory_windows` 和 `service_assessment_windows` 入口在代码中均明确 `DIAGNOSTIC_ONLY`/`backup_or_migration_authorized=false`，不能升级为停写证明。维护状态与合成数据可在隔离PG验证，但目标账户、SCM真实服务、旧程序版本、文件句柄/DB会话和人工备份恢复的现场证据缺失。因此当前不能实现一个会在此机真实允许 Migration 的正式升级入口；保留 Migration 关闭，不能报告完整升级 PASS。

不依赖这些前置的发行工作继续：现有前端/后端候选 ZIP 的内嵌运行时为93发行元数据；P05-P02-A02 已验证的联合 OCRmyPDF 嵌入式运行时为106项，位于另一个被Git忽略的构建目录。旧候选不含这13项，不能把其 OCR 兼容性描述成已入包。下一项按原产品 Scope 用106项运行时、已固定原生/模型输入和许可材料组装全新**非发行**端到端候选，清洁解包验证；正式发行仍受法律、质量、签名、账户/三平台/Gate阻断。升级入口后续在目标服务/账户环境具备时恢复；不改变原冻结方案或公开客户数据。

【待确认】问题：正式部署账户、三项PLM服务及旧版进程静止/备份恢复现场证据当前不可取得。影响：不能允许真实现网升级/Migration。当前可选方案：继续本机非发行包组装与隔离验证；在目标环境具备后执行服务/备份/升级验收。建议：先完成可复核包及工具，目标环境到位时按同一流程验收。是否阻塞：阻塞本项正式升级放行，不阻塞其他已批准WBS。
