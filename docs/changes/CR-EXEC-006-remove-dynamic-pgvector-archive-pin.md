# CR-EXEC-006：移除动态生成的 pgvector ZIP 字节摘要依赖

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005、PR #52、WBS PLT-PKG-01-A09-P51-A17
- 范围：仅调整 Windows PostgreSQL 18.6 / pgvector 0.8.6 云端重建的源码身份校验方式。

## 背景与偏差

首轮 GitHub Actions Windows Server 2025 构建下载并通过了固定大小与 SHA-256 的 EDB PostgreSQL 18.6 二进制包校验。随后从 GitHub 标签归档 URL 下载的 pgvector 0.8.6 ZIP 实际返回约 210.5 KiB，与仓库历史登记的 214,357 字节及摘要不符，流程按失败关闭规则停止，未继续编译或上传产物。GitHub 自动生成的 source archive 不作为稳定的字节级制品。

## 决策

改用 pgvector 官方 Git 仓库的固定提交 `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c` 作为源码身份，并通过浅克隆固定标签后核验完整提交 SHA。移除动态 ZIP 下载及其历史字节摘要依赖。保留对 EDB 二进制包的固定大小和 SHA-256 校验，并继续对编译后的 DLL、许可证文件、运行时载荷及最终 ZIP 执行摘要校验。

## 影响与风险

- 保留版本与来源约束，变更的是上游 ZIP 字节身份到 Git 提交身份；构建时仍需要 GitHub 可达。
- 若标签不再指向固定提交，构建停止，不允许自动跟随新提交。
- 该变更只允许产生新摘要的非发行候选组件，不改变正式发布状态、法律审核状态或 Gate 结论。

## 验证与回退

重新运行 Windows Server 2025 GitHub-hosted Actions：验证固定 EDB ZIP、克隆并核验 pgvector 固定提交、编译、构建候选 sidecar、读回包内每个文件并核验摘要。失败时按日志修复或保持阻塞；回退时恢复 CR-EXEC-005 原脚本版本，不覆盖历史提交。

## 状态

本 CR 在代码修改前登记。首轮失败证据为 workflow run `40448939068`，job `122006805375`，停止于 pgvector 动态 ZIP 大小/摘要检查。