# PLT-PKG-01-A05：Windows Python 离线运行时来源与完整性

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；仅发行准备，不关闭 Gate。
- 当前 WBS：PLT-PKG-01-A05。
- 输入基线：V2.1 Python 3.13.x/Win11 与 Server2025 x86-64、A01～A04 候选包、Python 官方 3.13.15 Windows AMD64 embeddable 包及官方许可。
- 前置任务：A04 只依赖本机预装 Python 完成候选重装，明确缺包内运行时；本项用于补齐可审计运行时来源。
- 涉及模块：发行准备工具与 Git 忽略的本地运行时资料，不改业务代码、实体、Migration、API 或权限。
- 验收标准：只接受官方固定版本 AMD64 ZIP，SHA-256 与官方发布值相符；ZIP 路径/文件检查；隔离解包后 `python.exe` 为 3.13.15/AMD64，`LICENSE.txt` 存在；报告不含本机 Secret/客户数据。
- 风险：嵌入式包不含 pip、Microsoft C Runtime 或第三方包；不能直接复用 A04 venv 重装结论。第三方依赖须由安装器旁装并实测，正式发行仍需 Third Party License/SBOM、三平台和完整安装验收。

## 官方依据与决策

- 3.13.15 发布页列出 Windows embeddable package (64-bit) SHA-256：`d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`。来源：<https://www.python.org/downloads/release/python-31315/>。
- Python 3.13 Windows 文档说明嵌入式包适合随应用携带，但不含 pip；第三方包应由应用安装器旁装。来源：<https://docs.python.org/3.13/using/windows.html#the-embeddable-package>。
- PSF License V2 允许符合条件的再分发，需保留许可/版权通知；Python 中还含第三方许可。来源：<https://docs.python.org/3.13/license.html>。
- 决策：只将经官方校验的原始嵌入式 ZIP 作为 Windows 运行时候选；不复制本机 Python 安装目录，不在目标机依赖在线 pip。此为尚未锁定具体发行形式的内部打包选择，不变更 Python 3.13 技术栈。第三方包旁装与运行时整合另设后续验证；当前不得改变 `release_eligible=false`。

## Windows 11 执行结果

```powershell
& .\tools\verify_windows_python_runtime.ps1 `
  -Archive 'artifacts/package-prep/windows11/python-runtime-20261001-3.13.15/python-3.13.15-embed-amd64.zip'
& .\tools\tests\test_verify_windows_python_runtime.ps1
```

- 2026-10-01 从 `https://www.python.org/ftp/python/3.13.15/python-3.13.15-embed-amd64.zip` 下载到 Git 忽略目录；11,009,825 字节，SHA-256 `d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf` 与发布页一致。
- 首次按目录中另一名称 `python-3.13.15-embeddable-amd64.zip` 下载（11,010,501 字节，SHA-256 `791ada5e20aba24524f8d939cdeb069976d632a699fe5cb65274b23f4545e68a`），与发布页不符，因此未解包、未入候选包。源目录确实列有两个名称；选择发布页校验值对应的 `embed-amd64.zip`，保留前者仅作本地诊断，不提交 Git。
- 正确 ZIP 34 个顶层文件，包含 `python.exe`、`python313.dll`、`python313.zip`、`python313._pth`、`LICENSE.txt`。隔离解包后执行身份检查为 Python 3.13.15/AMD64，`sys.path` 只在该私有运行时目录，许可通知存在；本机 `System32/ucrtbase.dll` 存在，但这不能代替 Server2025/干净 Win11 安装验收。验证目录为 `artifacts/package-prep/windows11/python-runtime-verified-20261001-002137-f3a5b67b/`。
- 2/2 合成负例在解包前拒绝：错误名称、正确名称但错误 SHA-256。嵌入式解释器 `-m pip` 返回 `No module named pip`，与官方说明一致；A04 的新 venv 重装结果不能直接迁移为该运行时的第三方包结论。
- 结论：`WINDOWS11_PYTHON_EMBED_SOURCE_PASS / INTEGRATION_PENDING`。本项只关闭官方来源/Hash/许可文件/纯运行时身份，不将其加入 A03 旧候选 ZIP；后续需旁装并实测 93 wheel 的第三方包、原生扩展、OCR、服务入口及 Third Party License。`release_eligible=false`、Gate3/Release OPEN。
