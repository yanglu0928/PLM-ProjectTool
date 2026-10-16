# PLT-PKG-01-A06：Windows 嵌入式运行时旁装后端依赖

## 编码前检查

- 当前 Phase：Phase 2 Platform Core，发行前置验证，不关闭 Gate。
- 当前 WBS：PLT-PKG-01-A06。
- 输入基线：A01 的 93 wheel/逐文件 Hash，A05 官方 Python 3.13.15 AMD64 embed ZIP/发布页 Hash，Python 官方 embeddable 第三方包旁装说明。
- 前置任务：A01/A05 已本机 PASS；A04 证明同批 wheel 可在普通 venv 从包内无索引安装，但不证明 embed 解释器兼容。
- 涉及模块：Git 忽略的 Windows 私有运行时实验目录和发行准备脚本；不改生产业务实体、Migration、API 或权限。
- 验收标准：输入 wheelhouse/运行时逐文件验证；仅构建机 Python/pip 在离线索引模式将 wheel 安装到私有 `packages`；嵌入式解释器 `._pth` 仅引入该目录、目标机无需 pip；验证 FastAPI/SQLAlchemy/psycopg/PaddleOCR/本包及 Windows 服务入口导入，禁止搜索路径逃逸。
- 风险：构建机 `pip --target` 旁装不等于客户机完整安装；原生 DLL、Paddle OCR 模型、VC/UCRT、服务账户、Server2025 和许可清单仍需独立实测。失败不加入候选包；实验目录新建且不改已有 A01/A05 输入，可撤脚本/实验目录回滚。

## Windows 11 执行结果

```powershell
$builder = py -3.13 -c 'import sys; print(sys.executable)'
& .\tools\build_windows_embedded_backend.ps1 `
  -RuntimeArchive 'artifacts/package-prep/windows11/python-runtime-20261001-3.13.15/python-3.13.15-embed-amd64.zip' `
  -BackendRunRoot 'artifacts/package-prep/windows11/backend-20260930-230837-1ff07b2b' `
  -BuilderPython $builder
& .\tools\tests\test_build_windows_embedded_backend.ps1 `
  -RuntimeArchive 'artifacts/package-prep/windows11/python-runtime-20261001-3.13.15/python-3.13.15-embed-amd64.zip' `
  -BuilderPython $builder
```

- 2026-10-01 Windows11：重新验证 A05 官方 ZIP SHA-256 和 A01 93/93 wheel Hash，构建机 Python3.13 x64 用 `pip --no-index --only-binary=:all: --ignore-installed --target` 旁装至新建私有 `runtime/packages`。最终 Git 忽略实验目录：`artifacts/package-prep/windows11/embedded-backend-20261001-003655-949d77fb/`，未复制到 A03 候选 ZIP。
- 修改仅生成物 `python313._pth`，保留 `python313.zip`、`.` 并新增相对 `packages`；不启用 `site`。嵌入式 Python 中 93 个 `.dist-info`、本包版本 `0.1.0.dev0`、FastAPI/SQLAlchemy/psycopg/Paddle/PaddleOCR/PaddleX 与 Windows 服务入口导入 PASS；`pip` 不存在，`sys.prefix`/`sys.path` 仅在私有运行时。另清除 `PYTHONPATH` 并把 `PATH` 限制在私有运行时与 Windows 系统目录，原生导入再次 PASS。
- 首次实验在导入成功后被 Paddle 的额外 stdout 提示干扰 JSON 报告解析；已让脚本只解析目标 JSON 行并重新全程通过。输入负例 2/2：运行时坏 Hash、wheelhouse 数量不符，均在安装前拒绝。
- 结论：`WINDOWS11_EMBEDDED_BACKEND_IMPORT_PASS / RELEASE_BLOCKED`。约 890MB 私有运行时仅为当前本机实验；未执行 OCR 模型推理、真实服务/Session/License/数据库、物理断网、完整客户安装或升级。Third Party License/SBOM、正式信任源、Server2025/Debian13、Gate3～7 仍待；A03 `release_eligible=false` 不变。
