# POC-01 Python 3.13 依赖矩阵

## Status

`PASS_WITH_EXCEPTION`

Windows 11 与 Windows Server 2025 的必需检查均已通过。根据用户 2026-09-17 的明确决定，Debian 13 本轮验证暂缓并登记为例外；该状态不表示 Debian 13 已验证或已兼容。

## Objective

证明项目核心 Python 依赖能够在 Windows 11、Windows Server 2025 与 Debian 13 的 Python 3.13.x 环境中完成在线制品准备、完全离线安装、import 和最小功能运行。

## Environment

正式目标：

- Windows 11 x86-64，Python 3.13.x。
- Windows Server 2025 x86-64，Python 3.13.x。
- Debian 13 x86-64，Python 3.13.x。

已验证环境包括 Windows 11 Home 10.0.26200 x86-64，以及 Windows Server 2025 Datacenter 10.0.26100 x86-64；两端均使用 Python 3.13.15。根据 V2.1 基线，这两个环境属于正式目标平台；当前 POC-01 的 Windows 子项已通过，但不代表完整发行 Gate 已通过。完整环境状态见 `docs/poc/environment-matrix.md`。

## Input

- `requirements/core.txt`：API、ORM、Migration、PostgreSQL 客户端和 pgvector 客户端。
- `requirements/document.txt`：PDF、Word、PPT、XLSX 解析/生成依赖。
- `requirements/ocr.txt`：PaddleOCR、PaddlePaddle、Tesseract Python wrapper、OCRmyPDF。
- `requirements/all.txt`：完整组合入口。
- Python 3.13.x 官方运行时。
- Tesseract、Ghostscript 等 OCRmyPDF 所需系统组件。

## Steps

### Windows 在线预检

```powershell
.\scripts\windows\run-online-validation.ps1
```

### Windows 构建离线 wheelhouse

```powershell
.\scripts\windows\build-wheelhouse.ps1
```

### Windows OCR 系统组件与回归验证

```powershell
.\scripts\windows\prepare-tessdata-best.ps1
.\scripts\windows\install-ghostscript-portable.ps1
.\scripts\windows\run-ocr-validation.ps1
```

将整个 `artifacts/poc-01/windows/` 复制到断网的 Windows 11 或 Windows Server 2025 后；通过 `EvidencePlatform` 分别记录证据：

```powershell
.\scripts\windows\run-offline-validation.ps1 -WheelhousePath <wheelhouse目录> -EvidencePlatform <windows-11或windows-server-2025>
```

### Debian 13 在线预检

```bash
bash scripts/linux/run-online-validation.sh
```

### Debian 13 构建并验证离线 wheelhouse

```bash
bash scripts/linux/build-wheelhouse.sh
bash scripts/linux/run-offline-validation.sh <wheelhouse目录>
```

## Result

|检查项|Windows 11 本机预检|Windows Server 2025|Debian 13|
|---|---|---|---|
|Python 3.13 运行时|PASS（3.13.15）|PASS（3.13.15 官方嵌入式包）|DEFERRED_BY_USER|
|隔离 Python 环境|PASS（venv）|PASS（portable runtime；系统策略禁止安装器）|DEFERRED_BY_USER|
|完整依赖安装|PASS|PASS（完全离线）|DEFERRED_BY_USER|
|import / 最小功能|15/15 PASS|15/15 PASS|DEFERRED_BY_USER|
|wheelhouse 构建|PASS（109 文件）|复用已校验 Windows wheelhouse|DEFERRED_BY_USER|
|完全离线安装|PASS（本机 `--no-index` 预检）|PASS（`--no-index`）|DEFERRED_BY_USER|
|Tesseract `chi_sim+eng`|PASS|PASS|DEFERRED_BY_USER|
|Ghostscript 10.08.0|PASS|PASS|DEFERRED_BY_USER|
|OCRmyPDF deskew + PDF/A-2b 中文扫描 PDF 主链|PASS（5/5 术语）|PASS（5/5 术语）|DEFERRED_BY_USER|

执行结果写入 `evidence/<platform>/`，并将非敏感摘要回填本文件。

## Metrics

|指标|目标|当前值|
|---|---|---|
|核心依赖安装成功率|100%|本机在线/离线均 100%|
|核心 import 成功率|100%|15/15|
|最小功能检查通过率|100%|15/15|
|断网安装网络请求数|0|本机使用 `--no-index`，0 次包索引请求|
|本轮要求的平台覆盖率|2/2|Windows 11、Windows Server 2025 PASS|
|正式目标平台累计实测覆盖率|3/3|2/3；Debian 13 `DEFERRED_BY_USER`|
|Windows wheelhouse 完整性|全部文件有 SHA-256|109/109|
|Windows 11 OCR 术语召回率|100%|5/5|
|Windows 11 PDF/A-2b|通过|PASS|
|Windows 11 deskew 编码兼容|无解码异常|PASS|
|Windows Server 2025 核心 import / 最小功能|100%|15/15|
|Windows Server 2025 OCR 术语召回率|100%|5/5|
|Windows Server 2025 PDF/A-2b / deskew|通过且无解码异常|PASS|

## Logs

- 在线环境采集：`evidence/windows-local/environment.json`
- 在线安装日志：`evidence/windows-local/install.txt`
- 在线验证结果：`evidence/windows-local/verification.json`
- 已解析包版本：`evidence/windows-local/resolved-packages.txt`
- wheelhouse SHA-256：`evidence/windows-local/wheelhouse-sha256sums.txt`
- 离线安装日志：`evidence/windows-local-offline/offline-install.txt`
- 离线验证结果：`evidence/windows-local-offline/verification.json`
- 中文 OCR 结果：`evidence/windows-11-ocr/result.json`
- 中文 OCR 输入/输出：`evidence/windows-11-ocr/input-scanned.pdf`、`output-searchable.pdf`
- 高精度语言模型 Hash：`evidence/windows-11-ocr/tessdata-best-sha256sums.txt`
- Ghostscript 尝试及备选方案：`evidence/windows-11-ocr/ghostscript-install-attempt.md`
- Ghostscript 最终安装证据：`evidence/windows-11-ocr/ghostscript-installation.md`
- Windows Server 2025 验证摘要：`evidence/windows-server-2025/README.md`
- Windows Server 2025 环境与依赖结果：`evidence/windows-server-2025/environment.json`、`verification.json`
- Windows Server 2025 OCR 结果：`evidence/windows-server-2025/ocr-result.json`

日志必须去除用户名、主机名、路径中的个人信息和任何 Secret 后才能提交。

## Known Issues

1. Debian 13 仍是正式兼容目标，但本轮验证已由用户明确暂缓；不得据此声称 Debian 13 已兼容。
2. PaddlePaddle/PaddleOCR 在 Debian 13 的 Python 3.13 wheel 可用性尚未验证；Windows 11 与 Windows Server 2025 已通过。
3. Windows Server 2025 的非管理员账号受系统策略限制，Python EXE 安装器返回 1625；已验证官方嵌入式 Python 的完全离线路径，正式安装器策略仍须在 Release Gate 单独确认。
4. Windows 编码兼容层挂接 OCRmyPDF 内部解析函数，升级 OCRmyPDF 时必须重新执行回归测试。
5. 当前 OCR 样本是合成基准；真实扫描件质量与准确率仍属于 POC-05。
6. 当前仓库仍为私有；Ghostscript 对外发行前必须完成 ADR-002 的源码公开、兼容许可证和第三方声明 Gate。

## Conclusion

POC-01 的 Windows 11 与 Windows Server 2025 子项均已通过：Python 3.13.15 离线依赖、15/15 项最小检查、Tesseract、Ghostscript 10.08.0、OCRmyPDF deskew 与 PDF/A-2b 中文主链均 PASS。依据用户批准的 `EXC-P0-001`，POC-01 以 `PASS_WITH_EXCEPTION` 收口并允许转入下一项 PoC；Debian 13 未验证风险保留到恢复验证或 Release Gate。真实扫描质量属于 POC-05，源码公开与 Ghostscript 发行合规属于 POC-09 / Release Gate。

## PASS / FAIL

`PASS_WITH_EXCEPTION`：本轮要求的两个 Windows 平台全部 PASS；Debian 13 经用户明确批准暂缓。此状态不是 Debian 13 的兼容性结论，也不能替代 Debian 发行验收。

## Alternative

若某个依赖失败，先输出 Failure Analysis、Root Cause、Impact、Option A、Option B 和 Recommendation。Python 3.12 仅是实施方案中规定的条件性候选方案，未经用户明确批准不得启用。
