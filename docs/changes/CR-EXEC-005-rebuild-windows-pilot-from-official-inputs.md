# CR-EXEC-005：从官方固定来源重建 Windows Pilot 运行时父包

- 日期：2026-10-27
- 状态：`RECORDED / SOURCE_INPUT_RECONSTRUCTION_READY_FOR_IMPLEMENTATION`
- 关联：`CR-EXEC-002`、`CR-EXEC-003`、`CR-EXEC-004`、`PLT-PKG-01-A09-P51-A17`

## 背景与偏差

A17 原构建流程把本机忽略区中的 P45 父 ZIP SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 作为唯一输入。二者不在 GitHub 仓库/Release，用户明确禁止在本机执行及上传既有 11.65 GiB stage。原固定输入因此无法在 GitHub runner 取得。

根据用户 2026-09-24 的持续自主执行授权及 2026-10-27 云端执行要求，本 CR 允许**在全新分支/新版本中**以官方公开制品、已固定版本/源码提交/组件摘要和仓库构建工具重建父包依赖，生成全新非发行父包。原 P45/P43/P33 等历史 SHA 与验证结论保持不变；绝不将新包伪称原包或覆盖其 provenance。新生成的每个来源输入与新父包均使用新摘要，并记录可复现的获取/构建步骤。

## 已核实来源与输入边界

- PostgreSQL 18.6 Windows installer/binary archive、pgvector 0.8.6 官方源码 tag/commit 与各输入摘要已在 POC-02 manifest/脚本固定。
- Paddle OCR det/rec 模型各自精确 revision 和五个 Git/LFS 对象 ID 已固定于 `tools/audit_paddle_model_revisions.py`。
- Windows Python 3.13.15 embed archive、Ghostscript 10.08.0 installer/官方源码 tar.xz、Caddy v2.11.4 Windows release/source/SBOM、Go 1.26.3 官方源码已有固定摘要/来源记录。
- 34 项无 JBIG Tesseract 矩阵列出 MSYS2 包名/版本及 package/source 摘要；多数二进制来自固定 MSYS2 package archives，libtiff 为固定上游源码构建。矩阵及 61 条许可证文本来源映射已提交。
- 当前仓库已有的 P10/P12/P15/P22/P33/P43/P45 ZIP 和运行时/原生/模型离线目录不在 GitHub。需要从上述来源重新形成新谱系，不假定原 ZIP 摘要可以复现。
- 详见 `docs/progress/plt-pkg-01-a09-p51-a17-source-rebuild-input-audit.md`；其中保留尚待实现验证的来源解析和 runner 资源检查项。

## 范围、验收及恢复

本 CR 仅允许重新构建非发行离线候选及相应下载/来源审计/组装工具/云端工作流。产品业务/API/Schema/Migration/权限无变更；不接触客户数据、正式 License 私钥、用户密钥、正式数据库、SCM/服务或系统安装根。所有下载须有来源 URL、版本/commit、长度/摘要验证；所有组装在 GitHub 托管 Windows runner 唯一临时目录，先检查剩余空间，失败时保留诊断摘要、不继续写入/安装。构件继续标记 `release_eligible=false`、`legal_clearance=false`。

验收依序要求：官方输入固定摘要通过；独立核验新父包完整来源树、文件全集和哈希；当前源码后端 wheel/前端 dist/pgvector 注入同一提交并验证；在新 ASCII 临时目录清洁解包；只启动本次 runner 拥有的 PG18/HTTPS/API；合成 Edge 完成 A17 PlanVersion 流程；SQL/Audit/Receipt/Decision 计数满足 A17；清理本次资源且最终候选摘要不变。法律/正式信任/Windows 11 实机/Pilot/Gate/正式发行仍独立开放，不因构建 PASS 自动关闭。

若任一输入不可取得、来源与哈希不符、runner 资源不足或编译结果无法验证，停止该组件并记录偏差，保留历史候选；可对可复现部分继续推进，不降低验收或标记通过。回滚为弃用全新候选/工作流，不删除或改写旧输入与历史证明。
