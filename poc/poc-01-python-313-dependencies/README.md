# POC-01 Python 3.13 依赖矩阵

## Status

`IN_PROGRESS`

目标平台尚未全部可用，因此当前不得判定 PASS 或 FAIL。

## Objective

证明项目核心 Python 依赖能够在 Windows 11、Windows Server 2025 与 Debian 13 的 Python 3.13.x 环境中完成在线制品准备、完全离线安装、import 和最小功能运行。

## Environment

正式目标：

- Windows 11 x86-64，Python 3.13.x。
- Windows Server 2025 x86-64，Python 3.13.x。
- Debian 13 x86-64，Python 3.13.x。

当前环境：Windows 11 Home 10.0.26200 x86-64，Python 3.13.15。根据 V2.1 基线，该环境属于正式目标平台；当前结果计入 Windows 11 的 Python 包子项，但不代表该平台全部系统依赖已通过。完整环境状态见 `docs/poc/environment-matrix.md`。

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
|Python 3.13 运行时|PASS（3.13.15）|BLOCKED_ENVIRONMENT|BLOCKED_ENVIRONMENT|
|创建隔离 venv|PASS|NOT_RUN|NOT_RUN|
|完整依赖在线安装|PASS|NOT_RUN|NOT_RUN|
|import / 最小功能|15/15 PASS|NOT_RUN|NOT_RUN|
|wheelhouse 构建|PASS（109 文件）|NOT_RUN|NOT_RUN|
|完全离线安装|PASS（本机 `--no-index` 预检）|NOT_RUN|NOT_RUN|

执行结果写入 `evidence/<platform>/`，并将非敏感摘要回填本文件。

## Metrics

|指标|目标|当前值|
|---|---|---|
|核心依赖安装成功率|100%|本机在线/离线均 100%|
|核心 import 成功率|100%|15/15|
|最小功能检查通过率|100%|15/15|
|断网安装网络请求数|0|本机使用 `--no-index`，0 次包索引请求|
|目标平台覆盖率|3/3|Windows 11 Python 包子项通过；完整平台 0/3|
|Windows wheelhouse 完整性|全部文件有 SHA-256|109/109|

## Logs

- 在线环境采集：`evidence/windows-local/environment.json`
- 在线安装日志：`evidence/windows-local/install.txt`
- 在线验证结果：`evidence/windows-local/verification.json`
- 已解析包版本：`evidence/windows-local/resolved-packages.txt`
- wheelhouse SHA-256：`evidence/windows-local/wheelhouse-sha256sums.txt`
- 离线安装日志：`evidence/windows-local-offline/offline-install.txt`
- 离线验证结果：`evidence/windows-local-offline/verification.json`

日志必须去除用户名、主机名、路径中的个人信息和任何 Secret 后才能提交。

## Known Issues

1. Windows Server 2025 和 Debian 13 验收环境尚未提供。
2. PaddlePaddle/PaddleOCR 在 Windows Server 2025 与 Debian 13 的 Python 3.13 wheel 可用性尚未验证；Windows 11 已通过。
3. OCRmyPDF 依赖的 Tesseract、Ghostscript 等系统组件尚未验证。
4. 当前验证只覆盖包安装、import 和不依赖外部程序的最小功能；OCR 真实样本质量属于 POC-05。

## Conclusion

POC-01 已完成 Windows 11 / Python 3.13.15 的 Python 包在线与 wheelhouse 离线验证，全部 15 项检查通过。正式结论仍为 `IN_PROGRESS`；Windows 11 系统依赖以及 Windows Server 2025、Debian 13 的制品准备、断网安装和最小功能验证全部完成前，不得标记 PASS。

## PASS / FAIL

`IN_PROGRESS`：不是 PASS，也不是 FAIL。

## Alternative

若某个依赖失败，先输出 Failure Analysis、Root Cause、Impact、Option A、Option B 和 Recommendation。Python 3.12 仅是实施方案中规定的条件性候选方案，未经用户明确批准不得启用。
