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

## A43 云端重建结果（2026-11-02）

按本 CR 固定来源与禁止发行边界，GitHub hosted Windows run [41370951575](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370951575) 全12项job成功；PR #61 head `4cbf2c140a1515029e5823bba1bd6935a5c33399` 对应GitHub pull_request合并提交 `9713443955f7698a687c620ab3647971f8700847`。父包内ZIP SHA-256 `63ed5c8d209f09cb9fa22aeacf9245aeb8cfebf0cff8397beea26e591dc05a7a`、20,118个payload文件，artifact ID `13109214144`，容器摘要 `1a7ec0c2a26a8eb2252817598d5a83cb1c9e94d3b4e57968dcc808843168255b`。同run完成暂存/清洁包、PG18/pgvector临时生命周期、A17合成Edge/HTTPS/PG流与A34隔离替换/手动恢复。

该结果仅为 `PASS_LIMITED`。启动入口仍因数据库凭据拒绝；正式公钥/License trust/DB凭据身份/服务账户ACL/TLS仍缺，未安装或启动产品。没有Windows 11新运行、正式信任、法律放行、Gate、Pilot或Release结论。详见 `docs/progress/plt-pkg-01-a09-p51-a43-hosted-rebuild-result.md`。


## A44 云端结果（2026-11-02）

当前 PR 源码完整 run [41376505925](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925) 12/12 jobs success；A44包内非秘密 Pilot readiness report通过缺项、完整但不授权、非法值不回显三组实测；A17/A34/PG smoke同run成功。父包内ZIP SHA-256 `8e3e4e37224ad3653c2f2d758d024e23a5c6591fde89cb85efd375bc304f801d`，20,122 files。PR head `f182eb37cb572da99b6615746655d7c7a0e2b30c` 对应 merge commit `325ce2e90b298d657ca3acceb98bcb8a54968abe`。见 A44 进度结果。未提供正式产品信任，Pilot/Gate/Release不变。


## A45 结果（2026-11-02）

当前固定来源重建流程在 hosted Windows Server 2025 run [41378263123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41378263123) 12/12 jobs成功。新父ZIP SHA-256 `e2858a6b6af852ada906e84671b539dee25c2571387940e4680346dd2c0256ca`、20,122 files；A17 29 API合成PlanVersion流、A34替换/恢复和PG18/pgvector通过。仅证明 hosted Windows Server 2025，不是Windows 11实测或release。正式信任与启动阻断仍保持。


## A46 云端结果（2026-11-02）

Hosted Windows Server 2025 run [41382282100](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41382282100) 全12 jobs成功。父包可读模式对不完整/完整/无效输入三态实测，UTF-8中文提示正确，完整仍不授权、秘密哨兵不回显，默认JSON兼容。父ZIP SHA-256 `c9b6d945f359e6777396b6a12309c62b7deff141b0f6808f340d195a407164d3`，20,122 files。A17 29 API、A34显式恢复、PG18/pgvector通过。未进行Windows 11新测试；Pilot/Gate/Release保持NOT_READY。


## A47 云端验收（2026-11-02）

Hosted Windows Server 2025 run [41383869172](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41383869172) 12/12 jobs成功。9项登记缺失均显示静态责任角色及下一步；完整/无效登记不授权且不回显注入值。父ZIP SHA-256 `1db6e14e10fb878cf290add82cb69b5ebd387ccaca783c0da23e2c6d1452d370`、20,122 files；A17/A34/PG smoke成功。该run不构成Windows 11新测试、Pilot/Gate或Release通过。


## A48 云端验收（2026-11-02）

Hosted Windows Server 2025 run [41386839114](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41386839114) 12/12 jobs成功。父包完整组合流程覆盖固定阻断顺序与零blocker+完整登记边界；后者仍需独立核验、所有授权布尔值false，正式manifest/hash保持不变。父ZIP SHA-256 `8e642dc1c4393fdae80935622349b094122b18509816fc8ce4a9d7805aa48948`，20,122 files。A17/A34通过；不构成Windows 11新测、Pilot/Gate或Release通过。
