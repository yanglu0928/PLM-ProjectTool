# PLT-PKG-01-A09-P51-A17：云端父包重建输入审计

日期：2026-10-27；关联 `CR-EXEC-005`。本记录只盘点输入来源，不表示父包构建或 A17 验收通过。

## 结论

固定 P45 父 ZIP 和 POC wheelhouse 文件本体均未进入 GitHub。各主要组件有已追溯的官方/上游输入，可按全新源谱系重建；但现有工具链仍把若干本机审计 JSON/ZIP 字节摘要作为硬性前置，必须改为重新运行来源审计并验证结构化字段，而不能直接搬用旧文件摘要。重建可行性最终以 GitHub runner 实测下载、剩余空间与输出哈希为准。

## 来源与当前证据

|组件|已登记来源和固定身份|云端重建状态/缺口|
|---|---|---|
|PostgreSQL|POC-02 `prepare-offline-assets.ps1` 固定 EDB PostgreSQL 18.6 installer、官方 Windows binary ZIP；POC manifest 给出大小和 SHA-256。|URL/身份在仓库。需要下载 binary ZIP，在 runner 中解包；installer 仅作为来源证据，不需在 runner 运行。|
|pgvector extension|官方 `pgvector/pgvector` v0.8.6，commit `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c`；仓库已有 VS build 脚本。|源码/二进制需 Windows runner 重建；原 P11 审计报告和 P12 ZIP 的固定摘要是旧本机产物，不能复用。|
|pgvector Python wheel|A17 原 wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`，文件未在仓库。|需从 PyPI 按 `pgvector==0.5.0` 重新下载并验证此摘要；不把不同 wheel 当作该输入。|
|Python embedded runtime|官方 `python-3.13.15-embed-amd64.zip` 固定 SHA-256 `d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`；106 发行版许可库存逻辑在工具中。|原 runtime 目录未提交；从官方归档重建运行时并从当前锁定依赖构建 wheelhouse，逐件生成新摘要。|
|前后端应用|PR #50 workflow 已在同一提交构建 wheel/dist 并以 artifact ID `12708379525`/`12708937093` 上传；更长期来源是当前 Git commit。|CI artifact 可短期下载，或在单次组装 workflow 中重建，确保来源提交相同。|
|Paddle OCR 模型|det revision `0d63e78e2b680928f6b1747d76a08db6e645efb7`，rec revision `682f20538d8c086cb2128e5cfac775e6c4904e85`；配置/模型 Git blob 与 LFS 对象 ID 全部固定于 `tools/audit_paddle_model_revisions.py`。|内容未在 repo。云端获取端点/对象下载并以现有审计器验证后，才能组模型包；运行时指纹必须保持 `511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4`。|
|Ghostscript|Artifex 官方 Ghostscript 10.08.0 Windows installer SHA-256 `52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50`；源码 tar.xz SHA-256 `c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf`。|官方链接与摘要已在 P43 记录；需要下载、独立审计并纳入新候选；不代表法律放行。|
|Caddy / Go|Caddy v2.11.4 发布资产及 Go 1.26.3 官方源码、SHA-256 已分别在 P19/P22/P32 记录。|重新取得公开发布资产及源码并验证，再生成新包分支；P22/P33 ZIP 本体缺失。|
|Tesseract / MSYS2 原生组件|无 JBIG 34 项矩阵 CSV 固定每个包名、版本、package/source SHA；例如 Tesseract `5.5.3-1`、libtiff 4.7.2。P45 两份 CSV 追溯 61 条精确许可文本。|MSYS2 package archives 可按包名/版本从官方仓库重取；libtiff 属固定源码构建输入。须通过现有 34 项 PE 摘要，且禁止静默加入 JBIG。|
|P45 谱系 ZIP|P10/P12/P15/P22/P33/P43/P45 的文件摘要记录留在进度文档和工具常量。|这些 ZIP 都未提交；任何新包都须建立新 manifest/摘要和来源父链，不声称重现旧 ZIP 字节。|

## 旧构建工具的不可直接重放点

1. `tools/package_windows_current_app_candidate.py` 固定 P45 与 pgvector wheel 哈希，支持函数级参数覆盖，但 CLI 不提供重建来源的摘要参数。
2. `tools/package_windows_unified_candidate.py` 把本机 P10 基础 ZIP、原生 ZIP、模型 ZIP、no-JBIG PE 目录作为固定输入；原输入中的若干目录未提交。
3. P11/P12 builder 进一步绑定旧 PoC bundle 和审计 JSON 的整份文件 SHA。重建时应由新云端审计器产生来源报告，验证其必要字段/所有官方输入摘要，再让构建器引用新报告哈希，避免要求本机旧 JSON。
4. 标准 GitHub Runner 可用磁盘必须在云端 job 内实测；构建只允许单一暂存树、顺序组装/清理，空间不足立即失败关闭。不可上传用户本机缓存或 stage。

## 下一步

在独立 feature 分支实现一个顺序的 Windows 2025 cloud rebuild job：先重取和验 PostgreSQL/pgvector 及模型输入，测量空间并保存仅来源清单/诊断；再串接 Python/OCR/Caddy/Go/Ghostscript，构造全新非发行父包。每阶段实际哈希/组件数均通过后才能继续同提交 wheel/dist 集成及 A17 合成 Edge/HTTPS/PG 流程。任何输入访问失败均作为具体来源/runner阻塞记录，不得降级为源码 CI PASS。
