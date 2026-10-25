# PLT-PKG-01-A04：Windows 11 候选 ZIP 重新解包与后端重装验证

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；本项仅发行前置验证，不进入 Release Gate。
- 当前 WBS：PLT-PKG-01-A04。
- 输入基线：V2.1 离线交付约束、PLT-PKG-01-A01/A02/A03 的本机非发行候选、当前 `0.1.0.dev0` 后端版本。
- 前置任务：A01 wheelhouse、A02 frontend dist、A03 候选载荷完整性均已本机通过；正式信任源不作为重装演练前置。
- 涉及模块：Windows 候选包验证脚本与本地被忽略测试目录；不改业务模块、实体、Migration、API 或权限。
- 验收标准：只接受明确的 `NOT-FOR-RELEASE` 候选；ZIP 入口无越界/重名/符号链接；实际解包文件与清单一一匹配且哈希正确；Python 3.13 x64 新 venv 从包内 wheelhouse `--no-index` 安装，`pip check`、本包/核心导入通过；前端 dist 存在且有 Hash。
- 风险：候选包本身仍缺正式 Python runtime、PostgreSQL、OCR 模型、License、公网/目标账户部署；本机包索引离线不等于物理断网或完整程序安装。新建独立目录演练，不触碰生产路径或现有 venv；失败保留证据，撤脚本/新建目录可回滚。

## Windows 11 执行结果

```powershell
$pythonExe = py -3.13 -c 'import sys; print(sys.executable)'
& .\tools\verify_windows11_candidate_reinstall.ps1 `
  -CandidateArchive 'artifacts/package-prep/windows11/candidate-20260930-233546-75a50316/NOT-FOR-RELEASE-windows11-candidate.zip' `
  -PythonExe $pythonExe
& .\tools\tests\test_verify_windows11_candidate_reinstall.ps1 -PythonExe $pythonExe
```

- 2026-10-01 Windows 11/Python 3.13.15 x64：ZIP SHA-256 `674d6dd94f8656482f983f72e2565f4ad98ad7364ef401c398e105b8a2096d9e`，从 ZIP 重新解包 97/97 载荷 Hash 一一匹配，93 个 wheel、新 venv 的 `pip install --no-index --find-links`、`pip check` 和 FastAPI/SQLAlchemy/psycopg/PaddleOCR/本包等导入 PASS。
- 实际被忽略的演练目录：`artifacts/package-prep/windows11/reinstall-20261001-000348-9bbcdccc/`；它仅供本机复核，不提交 Git 或交付客户。测试未运行生产 Migration、数据库连接、真实服务、OCR 模型推理或浏览器业务流程。
- 合成负例 3/3：越界 ZIP 路径、大小写折叠重名和非白名单条目均在解包前拒绝；测试目录已清理。
- 结论：`WINDOWS11_CANDIDATE_REINSTALL_PASS / RELEASE_BLOCKED`。包内不含 Python runtime/正式安装器、PostgreSQL18/pgvector、OCR 模型与系统组件、正式 License 公钥/客户 License、HTTPS/目标账户/Plugin/升级工具。`--no-index` 不等于物理断网；Server2025/Debian13、正式安装升级与 Gate3～7 未验。不得据此改变 A03 manifest 的 `release_eligible=false`。
