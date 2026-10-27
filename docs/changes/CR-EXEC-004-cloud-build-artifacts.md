# CR-EXEC-004：云端可下载构件与 A17 输入恢复

- 日期：2026-10-27
- 状态：`RECORDED / CLOUD_BUILD_ARTIFACTS_IN_PROGRESS / A17_PARENT_INPUT_BLOCKED`
- 关联：`CR-EXEC-002`、`CR-EXEC-003`、`PLT-PKG-01-A09-P51-A17`

## 背景与客观差异

用户要求本机不运行代码，尽量云端或沙箱执行。GitHub Actions 已在 GitHub 托管 Windows Server 2025 与 Ubuntu runner 上通过后端 3,849 项、前端 2,068 项、类型检查、构建和后端 wheel 构建。该验证未上传可下载构件。

A17 现有构建器必须输入 P45 父候选 ZIP SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98` 及 pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。两件均在本机 Git 忽略区，不在 GitHub 仓库或 Releases。不可将其上传到公开仓库，也不可用不同父件冒充已固定输入；本地既有 11.65 GiB stage 不上传。

## 选择与范围

先扩展现有云端验证工作流，在同一提交构建并保留后端 wheel、前端 dist、源码提交标识和 SHA-256 manifest，作为可审阅/下载的应用构件。构件仅含项目自身构建输出，不含运行时父包、客户数据、密钥、正式 License 信任材料或运行日志。保留现有测试矩阵和构建门槛。

这项是云端交付能力补强，不替代 A17 完整 Windows 内部试用包。Pilot 仍须在恢复或从可追溯官方来源重建完整父包后，执行清洁解包、Edge/HTTPS/PostgreSQL 集成旅程；未完成前不得声称包内验收或 Pilot 可用。

## 验收、风险与回滚

- 在 GitHub 托管 runner 中完成现有测试，并上传后端 wheel、前端 dist、构件清单；清单绑定同一 workflow commit，构件下载后摘要可核验。
- 检查构件不包含 Secret、客户资料、测试数据库、日志或本地配置。
- 失败时删除/弃用本 PR 与 workflow artifact 即可；不影响产品 API、数据库、历史候选或既有版本。
- API/Schema/Migration/产品运行行为：无变更。
- 兼容性：仅 GitHub Actions 云端构建；不构成 Windows 11、Windows Server 2025 或 Debian 13 应用运行兼容结论。
- 版本状态：开发构件，不是安装程序、不具备完整离线运行时，不可用于正式发行。

## 执行记录

待云端工作流修改、PR 独立检查与构件摘要检查完成后追加证据。A17 原固定父包输入的恢复/重建另行追溯，不得用本 CR 静默更改其固定摘要。
