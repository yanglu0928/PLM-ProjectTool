# PLT-PKG-01 当前后端离线依赖准备

## A01 编码前检查

当前 Phase：Phase 2 Platform Core（发行依赖前置，不进入 Gate6）。当前 WBS：PLT-PKG-01-A01。输入基线：V2.1 离线三平台交付、POC-01 Windows wheelhouse 方法、当前后端 `pyproject.toml` 精确依赖版本、DEC-548。前置：Python3.13 Windows11 环境和完整后端代码存在；真实 SCM/生产信任锚不是依赖集合检查前置。

涉及模块：后端构建与离线安装验证脚本，不改业务实体、数据库、公开 API 或依赖声明。实体：本地被忽略的 backend wheel、第三方 wheel 和 SHA-256 清单；不包含客户数据、配置或 Secret。权限：普通用户本地临时目录/构建目录，无 SCM、数据库或生产写操作。

验收标准：当前后端 wheel 与精确依赖仅由二进制 wheel 解析；Windows11 全新 Python3.13 venv 可用 `--no-index --find-links` 安装，`pip check` 和最低 import/元数据自检通过；生成确定性文件哈希清单，记录文件数/总字节数和测试结果。失败不能称离线可用，Server2025/Debian13 与完整包另验。

风险/回滚：Paddle/原生依赖可能缺匹配 wheel 或包体过大；`--no-index` 只阻断索引访问，不等于物理断网验证。脚本不自动修改依赖版本或引入源码构建；失败时停此任务并登记原因。生成物位于 Git 忽略目录，可在核对精确路径后清理；无 Migration/升级或业务数据影响。

## A01 Windows 11 执行结果

复现命令（从仓库根目录、指定 Python 3.13 x64 构建环境运行；脚本每次生成新目录）：

```powershell
& .\tools\build_windows_backend_wheelhouse.ps1 -PythonExe '<Python 3.13 x64 python.exe>'
```

- 输入：提交 `9c526cac` 的 `apps/backend/pyproject.toml`，Python 3.13 x64，脚本 `tools/build_windows_backend_wheelhouse.ps1`。构建不更改依赖声明或已安装系统。
- 本地运行目录（Git 忽略）：`artifacts/package-prep/windows11/backend-20260930-230837-1ff07b2b/`。保留 `wheelhouse/`、`sha256sums.txt`、`summary.json` 和全新 `verify-venv/`；不提交第三方二进制和虚拟环境。
- 结果：后端 wheel + 92 个依赖 wheel，共 93 文件、251,474,584 字节；93/93 SHA-256 重算与清单相符，清单文件 SHA-256 `cab7e2afb36a38a511b1a477932941bcd0fa5ffd955c1b73b35b39c4f2057618`，本包 wheel SHA-256 `1ef33b42b149766329d8eeb27402bcf11ab5c6dcf67c4fbc7e8aefa8671dc02f`。`pip download --only-binary=:all:` 完成，无第三方源包构建。新 venv `pip install --no-index --find-links` 成功，`pip check` 无冲突，FastAPI/Alembic/SQLAlchemy/psycopg、PyMuPDF、Office 文档库、Paddle/PaddleOCR/PaddleX 及本包版本导入检查通过。
- 结论：`WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS`，仅证明该次当前解析结果可在本机无包索引安装。测试期间构建/下载阶段仍使用网络与缓存；未物理断网，未复验 Windows Server 2025/Debian 13；OCR 系统组件、模型内容、PostgreSQL/pgvector、前端、Plugin、License/信任锚和端到端安装未在本任务内。传递依赖的未来重新解析未冻结，正式发行须固定并审查完整清单/许可。Gate3/Release 均不因本项关闭。

## A02 编码前检查：Windows 11 前端冻结锁离线构建

当前 Phase：Phase 2 Platform Core（打包前置，不进入 Gate6）。当前 WBS：PLT-PKG-01-A02。输入基线：V2.1 Vue3/TypeScript/Vite 与离线发行目标、已提交的 `apps/frontend/package.json`/`pnpm-lock.yaml`、DEC-549。前置：Node24、pnpm11 和当前前端源码齐备；A01 后端 wheelhouse 已内部通过但非本前端任务技术前置。

涉及模块：前端依赖获取与静态构建工具；无业务实体、后端 API/Schema 变化，不改 lockfile 或依赖版本。实体：独立 pnpm store、两份只含 Git 已提交前端源的隔离工作目录、dist 与 Hash 清单；全部位于 Git 忽略的 artifacts。

权限：普通本机文件/网络依赖获取；不触碰客户数据、Secret、SCM、数据库或当前开发 `node_modules`。验收：在线填充空的独立 store；在新源目录以 `--offline --frozen-lockfile` 安装，lockfile Hash 不变、前端测试/类型/构建通过，dist 非空且 Hash 清单可重算；结果仅 Windows11 包管理器离线模式，不等于物理断网或部署验收。

风险/回滚：平台原生 Node 包可能依赖 Win64 特定制品，store 与 lockfile 需精确配套；`pnpm install` 生命周期脚本及在线阶段可能访问网络。失败记实际原因，不改锁版本绕过；新建目录保留诊断，回滚只撤本任务脚本与忽略制品，不覆盖现有工作树。Server2025/Debian13 与完整程序包仍需独立验收。

## A02 Windows 11 执行结果

复现命令（仓库根目录、Node24 与 pnpm11.19.0）：

```powershell
& .\tools\build_windows_frontend_offline.ps1
```

- 输入：已提交源 `944bc7b2053b70d8704d9409bdc4eb4988288602` 的 `apps/frontend/`；脚本先拒绝脏前端工作树，再用 Git archive 生成两份全新源目录。未修改当前开发 `node_modules`、依赖版本或 lockfile。
- 本地运行目录（Git 忽略）：`artifacts/package-prep/windows11/frontend-20260930-232337-333c6e42/`，包括独立 pnpm store、在线填充源、第二份离线验证源、dist 与 SHA-256 清单；不提交 node_modules/第三方 store 二进制。
- Node `v24.17.0`、pnpm `11.19.0`；在线冻结锁阶段下载 157 包，第二份全新源目录 `pnpm install --offline --frozen-lockfile` 复用 157 包、下载 0 包。lockfile SHA-256 前后均为 `96ab30bab617bb1349eaf81a4143b22e57a6c3fc8500a06306c81e20c19fb468`。
- 离线装配后 Vitest 44 文件/1012 测试通过，`vue-tsc`/`tsc` 类型检查与 Vite 8.3.0 生产构建通过。dist 3 文件、319,425 字节；3/3 SHA-256 复算一致，清单文件 SHA-256 `9bbaa8aed5fd8a1628a6376b1a9e9dd7956faa5ff149832b67263008e4dc3a96`。
- 结论：`WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS`，仅证明本机固定 Node/pnpm 与锁文件下包管理器离线模式可从准备好的 store 重建并构建。在线阶段使用网络；未物理断网，也未验 Windows Server2025/Debian13、正式同源 HTTPS 静态部署、后端信任/License 或完整端到端程序包；Gate3/Release 均保持 OPEN。

## A03 编码前检查：Windows 11 候选载荷及缺项清单

当前 Phase：Phase 2 Platform Core（发行准备，不进入 Gate6）。当前 WBS：PLT-PKG-01-A03。输入基线：A01 后端 93 wheel/Hash 与 A02 前端 3 dist/Hash、DEC-550、V2.1 离线交付最小产物。前置：两次本机包管理器离线检查 PASS；正式服务/信任锚未齐备，因此只能组装非发行候选。

涉及模块：仅打包工具与候选目录，不改业务实体、数据库 Schema、公开 API 或依赖版本。实体：后端依赖、前端静态文件、非敏感配置示例、逐文件哈希和阻断清单；不得包含本地密钥/客户数据/日志/虚拟环境。

权限：普通本地文件读取及新建被忽略的 artifacts 子目录，无 SCM、数据库、生产安装/升级写入。验收：先逐条校验 A01/A02 源 Hash 与文件数量，拒绝越界/意外文件；仅复制明确白名单文件，装配后重算 Hash 并生成 manifest，固定 `release_eligible=false`、列明欠缺的运行时/系统组件/信任源/实机验收。任何错误不生成可误认的正式包。

风险/回滚：源制品来自不同开发检查点，虽应用代码未变但不能认定为同一次正式发行；未含正式公钥、运行时和安装器。候选目录必须与发行目录名称显著区分，不用于客户环境。撤工具及本次新建忽略目录即可回滚；无 Migration 执行或业务数据影响。

## A03 Windows 11 候选载荷结果

复现命令（从仓库根目录，对 A01/A02 的本地运行目录执行）：

```powershell
& .\tools\assemble_windows11_candidate_payload.ps1 `
  -BackendRunRoot '<A01 Windows11 backend run directory>' `
  -FrontendRunRoot '<A02 Windows11 frontend run directory>'
```

- 本地忽略目录：`artifacts/package-prep/windows11/candidate-20260930-233546-75a50316/`。其中 `NOT-FOR-RELEASE-windows11-candidate.zip` 为 247,855,179 字节，SHA-256 `674d6dd94f8656482f983f72e2565f4ad98ad7364ef401c398e105b8a2096d9e`；大型二进制不提交 Git。
- 入包前 A01 的 93 条 wheel Hash、A02 的 3 条 dist Hash 逐条验证；入包后 97 个文件（93 wheel、3 dist、1 非 Secret bootstrap 示例）/97 条 Hash 复算一致。ZIP 列表确认 `payload/`、`payload-sha256sums.txt` 和 `manifest.json` 都在包内。后端 wheel 中 Migration `20260930_0051` 可列出，未运行任何 Migration。
- `manifest.json` 固定 `kind=WINDOWS11_DEVELOPMENT_CANDIDATE_PAYLOAD`、`release_eligible=false`；列明 Python 运行时/安装器、PostgreSQL18/pgvector、OCR 系统组件/已批准模型、正式 License 公钥/客户 License、HTTPS/服务账户、Plugin、升级工具、三平台隔离验收和 Gate/UAT 仍缺。当前正式产品公钥资源并未随 wheel 供给，不能把测试公钥填入或将此包启动为正式客户实例。
- 结论：`PLT-PKG-01-A03 CANDIDATE_PAYLOAD_INTEGRITY_PASS / RELEASE_BLOCKED`。这只验证允许的开发制品在 Windows11 上能被完整、脱敏地组合与追溯，不证明安装、运行、升级、质量或正式发行。A01/A02 源代码检查点不同，正式发行需从同一已冻结提交重新构建并做完整验收。
