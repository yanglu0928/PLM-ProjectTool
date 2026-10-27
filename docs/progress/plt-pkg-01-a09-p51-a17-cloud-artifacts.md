# PLT-PKG-01-A09-P51-A17 云端构件交付旁路推进

日期：2026-10-27；关联 `CR-EXEC-004`。

## 现状与证据

A17 原计划依赖本机忽略区中的固定 P45 父 ZIP（SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`）和 pgvector wheel（SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`）。这些字节未提交到 GitHub 仓库/Release。原候选生成器严格校验摘要，因此当前 GitHub runner 无法重放完整 A17；本地执行已按用户最新指令停止。

## 本轮可交付改进

现有云端 CI 增加短期保存的 GitHub Actions 构件：
- Windows Server 2025 runner 生成后端 wheel 与来源提交/工作流/摘要清单；
- Ubuntu runner 生成前端生产 dist 与逐文件 SHA-256/来源提交清单；
- 两个构件均标记 `release_eligible=false`，保存 14 天；不包括完整运行时、PG18、OCR、客户数据或 Secret。

这些文件使同一源码提交的应用层构件可审阅和可下载，但不是安装包或完整内部 Pilot。分别运行的前后端 CI job 通过同一 `github.sha` 绑定来源；最终完整候选仍需 A17 固定父包或经新 CR 审查后重建父包，随后执行原定 Edge/HTTPS/PostgreSQL 旅程。

## 验收状态

PR 独立云端检查及 workflow artifact 摘要读取：待执行。未声称构建产物可运行或完成 A17。
