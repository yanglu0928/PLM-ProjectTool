# PLT-PKG-01-A09-P51-A17 云端构件交付旁路推进

日期：2026-10-27；关联 `CR-EXEC-004`。

## 现状与证据

A17 原计划依赖本机忽略区中的固定 P45 父 ZIP（SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`）和 pgvector wheel（SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`）。这些字节未提交到 GitHub 仓库/Release。原候选生成器严格校验摘要，因此当前 GitHub runner 无法重放完整 A17；本地执行已按用户最新指令停止。

## 本轮可交付改进

GitHub Actions 已生成并保存同一源码提交 `4bc8c7e9d0c33b32e5ac71ad249896ed7af5d4ad` 的短期云端构件：
- Windows Server 2025 runner：后端全套 3,849 项测试通过；wheel、来源/摘要 manifest 上传成功。Artifact ID `12707969411`，压缩构件 2,619,481 字节，GitHub SHA-256 `bc28c3600fedc99aeda3b3cedafccaed40e1a01181ee2cb31891a02f586cd168`。
- Ubuntu runner：前端 2,068 项测试、typecheck、生产构建、逐文件 SHA-256 manifest 与上传均成功。Artifact ID `12707834748`，压缩构件 524,180 字节，GitHub SHA-256 `e75bcd59f18054d112b52ac3184987eb929a83917b6582bde399886b95331102`。
- 两构件保留至 2026-11-10，均标记 `release_eligible=false`。未下载至本机。

这些文件使同一源码提交的应用层构件可审阅和可下载，但不是安装包或完整内部 Pilot。完整候选仍需恢复 A17 固定父包，或新建并批准可追溯重建父包的 CR，然后执行原定 Edge/HTTPS/PostgreSQL 旅程。

## 验收状态

PR #50 的 GitHub Actions run `40446503680` 结论 `success`，后端、前端测试/构建/manifest/上传步骤均完成。此证据只证明应用层开发构件被生成并存入 Actions artifacts，不证明构件已安装运行或满足 Pilot。