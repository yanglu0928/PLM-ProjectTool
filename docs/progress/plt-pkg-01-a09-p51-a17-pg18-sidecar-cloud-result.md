# PLT-PKG-01-A09-P51-A17：PG18/pgvector 首个云端重建结果

- 日期：2026-10-27
- 关联：CR-EXEC-005、CR-EXEC-006、PR #52
- 状态：PG18/pgvector sidecar 构建与包内摘要复核通过；同次完整仓库回归仍运行中。

## 偏差及处理

首轮 run `40448939068` 的 PostgreSQL 固定 EDB 二进制 ZIP（343,808,005 字节，SHA-256 `fbe23da234ee31547bf8a36d29dfd81e82b849df2d2b78d2eecb43d360252f8c`）校验通过。GitHub 标签 ZIP 与历史登记字节摘要不一致，构建在编译前安全停止，未上传产物。按事先登记的 CR-EXEC-006，改以 pgvector 仓库固定提交 `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c` 为源身份。

## 云端构建证据

GitHub Actions run `40449178288` / job `122007584583` 在 Microsoft-hosted Windows Server 2025 VM 上成功完成：

- 复核固定 EDB PostgreSQL 18.6 binary input。
- 克隆并校验 pgvector 0.8.6 固定提交。
- 使用 runner 中的 MSVC AMD64 工具链编译 `vector.dll`，并安装至临时 PostgreSQL 文件树。
- 生成新身份的 Windows PG18/pgvector 候选 runtime sidecar；打包器核对 PostgreSQL 版本、pgvector control 文件、许可证文本、路径/扩展名筛查、载荷清单及 ZIP 读回摘要。
- GitHub Actions artifact ID `12709910603`，名称 `plm-pg18-rebuilt-sidecar-4b81073e54b3827e58825869cb841db6eee406b6`，大小 55,943,334 bytes，SHA-256 `eb48d587b5790acd833604309a6f56bce54257c0ecd6d7523fa2e1b9eb53bd5d`，保留至 2026-11-10。

该 artifact 是云端生成候选材料，不是 GitHub 仓库中的发行包。产物内明确 `release_eligible=false`、`legal_clearance=false`；没有运行安装程序或启动 PostgreSQL 服务。

## 独立验收边界

本项通过仅表示：固定公开来源身份、Windows Server 2025 云端编译、非发行 sidecar 组包及包内摘要读回成功。它不表示安装/重启/备份/升级、真实服务账户与 ACL、离线安装、Edge/HTTPS/应用接入、正式法律审查、Gate 3、Pilot 或正式 Release 通过。

同一 run 的后端 3,849 项测试/wheel 与前端 2,068 项测试/typecheck/build 属完整源码 CI；记录本报告时，PG job 和前端 job 已通过，后端测试仍在执行。完整 run 结论待所有 job 完成。

## 后续

- 继续完成 run `40449178288` 全部源码 CI。
- 进入 A17 下一个独立组件：Python 3.13 embedded runtime 云端重建，依固定官方 ZIP 摘要和版本校验；不在本机执行。
- Python/OCR、Ghostscript、Caddy/Go、MSYS2 原生库及实际安装/应用集成继续作为后续独立任务，Pilot 与正式 Release 保持 NOT_READY。
