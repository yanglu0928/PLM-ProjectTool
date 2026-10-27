# CR-EXEC-004：云端可下载构件与 A17 输入恢复

- 日期：2026-10-27
- 状态：`CLOUD_BUILD_ARTIFACTS_VERIFIED / A17_PARENT_INPUT_BLOCKED`
- 关联：`CR-EXEC-002`、`CR-EXEC-003`、`PLT-PKG-01-A09-P51-A17`

## 背景与客观差异

用户要求本机不运行代码，尽量云端或沙箱执行。此前 GitHub Actions 已在 GitHub 托管 Windows Server 2025 与 Ubuntu runner 上通过后端 3,849 项、前端 2,068 项、类型检查、构建和后端 wheel 构建，但未保存可下载构件。

A17 现有构建器必须输入 P45 父候选 ZIP SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98` 及 pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。两件均在本机 Git 忽略区，不在 GitHub 仓库或 Releases。不可将其上传到公开仓库，也不可用不同父件冒充已固定输入；本地既有 11.65 GiB stage 不上传。

## 选择与范围

先扩展现有云端验证工作流，在同一提交构建并保留后端 wheel、前端 dist、源码提交标识和 SHA-256 manifest，作为可审阅/下载的应用构件。构件仅含项目自身构建输出，不含运行时父包、客户数据、密钥、正式 License 信任材料或运行日志。保留现有测试矩阵和构建门槛。

这项是云端交付能力补强，不替代 A17 完整 Windows 内部试用包。Pilot 仍须在恢复或从可追溯官方来源重建完整父包后，执行清洁解包、Edge/HTTPS/PostgreSQL 集成旅程；未完成前不得声称包内验收或 Pilot 可用。

## 验收、风险与回滚

- GitHub Actions run `40446503680` 全部成功。Windows Server 2025 runner 完成后端全套 3,849 项测试、wheel、来源/摘要 manifest 和上传；Ubuntu runner 完成前端 2,068 项测试、typecheck、生产构建、逐文件来源/摘要 manifest 和上传。
- 两构件均绑定源码提交 `4bc8c7e9d0c33b32e5ac71ad249896ed7af5d4ad`，GitHub artifact digest 可读取：后端 `sha256:bc28c3600fedc99aeda3b3cedafccaed40e1a01181ee2cb31891a02f586cd168`，前端 `sha256:e75bcd59f18054d112b52ac3184987eb929a83917b6582bde399886b95331102`。分别于 2026-11-10 03:55 UTC 与 03:53 UTC 到期（创建时 14 天保留）。
- 构件标签包含完整 40 位 commit，工作流中产出的 manifest 标明 `release_eligible=false`。当前证据未将构件声明为安装包、运行时包或 Pilot。
- 通过 workflow 输入与输出范围核查，构件仅包含项目构建目录，不包含客户资料、Secret、本地配置或运行日志；未将归档下载到本机。
- API/Schema/Migration/产品运行行为：无变更。
- 兼容性：仅云端构建能力；不构成 Windows 11、Windows Server 2025 或 Debian 13 应用运行兼容结论。
- 版本状态：开发构件，不是安装程序，不具备完整离线运行时，不可用于正式发行。
- 失败时可弃用本 PR 与短期构件；不影响产品 API、数据库、历史候选或既有版本。

## 执行记录

PR #50：`https://github.com/yanglu0928/PLM-ProjectTool/pull/50`。摘要、测试和上传步骤通过。A17 原固定父包输入的恢复/重建另行追溯，不得用本 CR 静默更改其固定摘要。