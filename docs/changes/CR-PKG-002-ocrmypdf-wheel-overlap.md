# CR-PKG-002：OCRmyPDF 与后端 wheel 闭包的单版本冲突

状态：`RESOLVED_FOR_NON_RELEASE_CANDIDATE`（正式发行仍待 Gate）；日期：2026-10-01；Phase 2 / `PLT-PKG-01-A08-P09-P05-P02`。依据用户 V1.1 持续授权先记录，再实施可撤回的非发行候选；不改 Gate 2 原冻结内容。

## 来源与证据

P05-P01 从 POC-01 的 109-wheel 固定来源选出 OCRmyPDF17.12.1 的 26-wheel 闭包，独立全新环境 `pip check` PASS。准备与既有正式后端 93-wheel 集并包时，按规范化包名逐件比对，唯一版本冲突为 `charset_normalizer`：后端候选 `3.5.2`，旧 PoC OCR 闭包 `3.5.1`。旧候选尚未接入 OCRmyPDF，不能把两份 wheel 同时放入同一候选后让安装器自行选择，也不能凭独立 PoC 的 PASS 宣称兼容。

## 方案与选择

- A（选择）：保持后端现有 `charset_normalizer 3.5.2` 固定来源/Hash，OCRmyPDF 新候选只补其他缺失轮子；以联合 wheelhouse 重新 `--no-index` 解析、全新 Python3.13 安装、`pip check`、嵌入式运行时导入和 OCR 命令复验。若版本约束/行为失败，则停止，不覆盖旧候选。
- B：将后端回退到 PoC 的 `3.5.1`。这会改变已验证的 93-wheel 后端锁及大量候选来源，影响面更大，当前不选。
- C：保持两个隔离 Python 环境。增加进程/安装/升级复杂度；只有 A 实测失败且有明确接口边界时再评估。

本 CR 不修改 `apps/backend/pyproject.toml`、生产 API/Schema/License/安全机制；只允许构造新的 Git 忽略非发行候选并保留旧 ZIP、旧 wheelhouse 和冻结提交。OCRmyPDF17.12.1 仍须保持固定；不从网络取更新版本。升级/回滚：旧候选原样保留，新候选失败直接弃用；正式安装/数据迁移未执行。验证要求包含 exact wheel 名称/Hash、联合解析、全新导入及中文 Windows `--deskew`/PDF-A 实测；若只能完成部分步骤，不宣称 P02 整体 PASS。

发行约束：此版本选择不解决 Tesseract/Ghostscript 原生来源、无效签名、AGPL/产品许可、受控 ACL/服务账户、真实独立质量或三平台验收，`release_eligible=false`。

2026-10-01/P05-P02-A01：按 A 逐件验 93+26 来源，唯一冲突确为 `charset_normalizer`；构造 106-wheel 联合集并在全新 Python3.13 x64 venv 无索引同时安装产品后端和 OCRmyPDF17.12.1，`pip check`、版本/导入通过。尚未嵌入运行时或执行 PDF/A-2b/`--deskew`，故 CR 保持 OPEN，发行状态不变。

2026-10-01/P05-P02-A02：联合106-wheel 一次性旁装至新官方嵌入式 Python，106 项元数据/私有导入/无 pip、干净 PATH PASS；显式接入本机 Tesseract/Ghostscript/ASCII tessdata 后，表格合成 PDF 的 PDF/A-2b、`--deskew`、术语5/5 PASS。`charset-normalizer 3.5.2` 保持不变。该特定版本冲突在非发行候选中解决，但原生组件、许可、正式 ACL、独立质量和三平台发行仍未通过；不得将 CR 状态解读为 Release Gate 通过。
