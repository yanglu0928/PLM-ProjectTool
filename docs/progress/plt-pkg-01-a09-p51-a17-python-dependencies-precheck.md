# PLT-PKG-01-A09-P51-A17：嵌入式 Python 依赖集成前置检查

- 日期：2026-10-27
- 状态：编码前检查通过。
- 前置证据：Python embed runtime artifact 12710141736 在 hosted Windows 2025 runner 通过；完整 workflow run 40450251167 后端/前端及两项运行时组件全部成功。
- 本项目标：将当前提交后端 wheel 和 Windows/Python 3.13 可用的固定直接依赖组装进已验证的 embedded runtime，完成干净进程导入验证并生成新的非发行候选包。

## 发现

- `apps/backend/pyproject.toml` 直接依赖均有精确版本，但仓库未提供 transitive dependency lock 文件。
- 旧 `package_windows_embedded_candidate.py` 绑定既有前端/后端 wheelhouse 摘要和 93 项 wheel、106 项最终 distribution；固定 P45 与 wheelhouse 本体不在仓库，不能直接复用。
- 当前 backend wheel 可由同一源码提交的 hosted CI 生成；Windows 2025 runner 能满足 Python 3.13/Windows wheel 平台，但最终以实际解析/安装/embedded import 为准。

## 实施方案

在独立的 hosted Windows 2025 job 顺序完成：
1. 从同一检出提交构建 backend wheel。
2. 根据该 wheel 元数据/pyproject 固定直接依赖，仅解析 Windows/Python 3.13 wheelhouse；拒绝源码构建分发。
3. 保存每个 wheel 的名称、版本、SHA-256 到构件清单；将 wheelhouse 安装到已校验的 embedded runtime `packages`，不携带 pip。
4. 核验 distribution 数量、许可证文件清单和禁用文件筛查；通过 clean isolated embedded Python 执行后端、FastAPI、SQLAlchemy、Paddle OCR 等真实 import。
5. 生成新摘要候选包并逐文件读回验证；artifact 标注 release/legal false。

transitive 解析结果以本次候选的哈希清单固定，不宣称旧 P45 摘要可复用；如安装结果揭示平台缺 wheel或依赖冲突，按证据记录 CR 并处理，不降低应用范围。

## 边界与回滚

只操作 GitHub-hosted Windows Server 2025 runner 的临时目录和14天 Actions artifact；不触碰用户本机。此项不包含 PG 集成、前端/原生/OCR 模型安装或用户可交付完整包。回滚只需丢弃本次新 artifact 并退回到单独 runtime base；历史构件保留。
