# PLM 第三方通知审阅草案

本草案供产品负责人和合格法律审阅人员核对离线发行材料。它基于 Windows 11 非发行候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5` 的实际文件及已跟踪审计矩阵；**不是最终 NOTICE、许可声明或发行批准**，不得直接放入交付包。当前既无产品级 `LICENSE`，也无产品级 `NOTICE`，且候选明确标记 `release_eligible=false`。

此页保留 P43 历史候选的审阅基线；包含原生 OCR 42 份正文与 61 条映射的新 P45 候选另见[当前候选审阅草案](THIRD-PARTY-NOTICE-REVIEW-DRAFT-P45.md)及[可直接读取的原文字节](native-ocr-p45-review-inputs/REVIEW.md)。两个候选均不可发行，不应把新材料反写到旧 ZIP 的事实中。

## 已具备的材料与仍需复核的范围

|组件范围|候选内已定位的证据|审阅未完成的事项|
|---|---|---|
|Ghostscript 10.08.0|`payload/ocr/ghostscript/doc/COPYING`、同版官方源码归档及源包 `LICENSE`|确认本产品分发方式、完整对应源码与其他内含组件义务，以及最终通知和获取源码方式；现有文件不等于法律放行。|
|Caddy 2.11.4 与 Go 1.26.3|Caddy `LICENSE`、149 组件 SBOM、可构建源码；Go 标准库源码及 `LICENSE`|逐项复核 Caddy 下游依赖的许可、归属和通知，不以根许可证代替全部 149 项。|
|PostgreSQL 18.6 与 pgvector 0.8.6|服务器许可文本、命令行工具第三方许可文本、pgvector `LICENSE`|复核实际发行物、归属声明及随包其他原生依赖的要求。|
|Python 分发包|106 个已登记分发包，其中 1 个是本产品后端、105 个为第三方；历史独立通知材料 152 份，OCR 新增通知材料 25 份|105 个第三方包逐项匹配名称、版本、许可文本及通知；其中 60 个没有明确的 `license_expression` 元数据。|
|前端|6 份独立许可侧载|逐项核对实际生产依赖与归属通知；当前标记仍是 `REVIEW_REQUIRED`。|
|原生 OCR 依赖与模型|34 项原生 PE 的来源/许可证据矩阵，Paddle 模型说明文件|34 项 `release_obligations_reviewed` 均为 `NO`；模型与随包字节、归属和通知仍需逐项复核。|

[34 项原生 PE 精确材料映射](../progress/plt-pkg-01-a09-p45-a01-native-pe-review-inputs.md)已确认各二进制字节与来源矩阵一致；矩阵的 61 条许可文本记录未形成候选内的原生组件专属通知。其他 Python 包材料中偶有相同正文，不可替代原生 PE 归属映射。

[原始来源字节核验](../progress/plt-pkg-01-a09-p45-a02-native-license-source-bytes.md)已从固定 MSYS2 包/上游源码归档读回全部 61 条矩阵文本，得到 42 个不同正文哈希；这是新候选侧载的技术输入，尚未改旧包或形成已批准的原生 NOTICE。

[P45-A03 新非发行候选](../progress/plt-pkg-01-a09-p45-a03-native-ocr-notice-candidate.md)已另行侧载 42 份去重原文及 61 条逐组件映射，原 P43 候选及本草案的基准 SHA 不变。该技术材料仍未取得许可证适用性、产品最终 NOTICE 或发行法律审结；新候选的 `release_eligible=false`。

第三方证据目录共有 190 个文件，其中包括许可证文本、SBOM 与校验文本；“190”不是已审结的许可证数量。源码目录有 Caddy、Go 标准库和 Ghostscript 三份归档。候选字节和数量的复核见 [发行证据差异记录](../progress/plt-pkg-01-a09-p43-a06-release-obligation-delta.md)；[Caddy 149 项审阅队列](../progress/plt-pkg-01-a09-p29-caddy-sbom-review-queue.csv)和[34 项原生 PE 矩阵](../progress/plt-pkg-01-a08-p09-p05-p03-a07-p03-no-jbig-license-evidence.csv)保留逐项来源。

## Python 通知材料的明确缺口

新的[通知输入核对工具](../../tools/audit_notice_draft_inputs.py)把本产品后端从 106 个分发包中剔除，得到 105 个第三方包。下列三项没有嵌入式通知文件：`bce-python-sdk`、`et_xmlfile`、`openpyxl`。后两项另有固定候选中的独立 wheel 许可侧载；`bce-python-sdk 0.9.79` 在该候选内未找到独立通知材料。此前对其[精确版本源码与声明的核查](../progress/plt-pkg-01-a08-p04-bce-exact-source.md)不能代替适用于该发行物的许可文本审阅。

[bce 精确材料复核](../progress/plt-pkg-01-a09-p43-a08-bce-license-text-reuse.md)确认：候选已有一份 `payload/third-party-licenses/caddy/LICENSE`，内容与 Apache 官方 2.0 正文逐字节一致；bce 的包元数据声明 Apache License 2.0。因此可把这份现有通用正文列为 bce 文本复用的**审阅候选**，无需在现阶段复制一份相同字节。该文件仍以 Caddy 路径侧载，不能据此声称 bce 的归属映射、专属通知或最终发行许可义务已经满足。

另有 60 个第三方包的 `license_expression` 元数据为空。这不等于它们没有许可证；只表示不能从该字段直接确定通知内容。工具逐名输出清单，审阅时须结合包内文件、已侧载文本及确切版本来源逐项确认。上述 105 个第三方包的既有 `review_status` 均仍为 `REVIEW_REQUIRED`。

[60 项精确材料映射](../progress/plt-pkg-01-a09-p43-a09-python-license-gap-review.md)进一步区分 57 项有嵌入通知、2 项仅有独立侧载、1 项无该分发包专属通知；旧式 `License` 字段与许可证分类器只作为辅助线索。该分类不推定这些文本已覆盖全部子组件、归属或发行义务。

[105 项完整 Python 审阅输入](../progress/plt-pkg-01-a09-p43-a10-python-105-review-inputs.md)已将另外 45 项的 `License-Expression` 和 `License-File` 逐包核对并合并前述 60 项；102 项有嵌入材料、2 项仅侧载、1 项无专属材料。此清单便于逐组件复核，但所有行仍标记 `REVIEW_REQUIRED`，不能替代最终产品级通知或法律签核。

## 发布前必须明确的决定和证据

产品负责人及合格法律审阅人员应先确定本产品的对外许可与分发模式，并据此确认 Ghostscript、其他第三方组件和本产品代码之间的适用边界。Artifex 的[许可说明](https://artifex.com/licensing)将其产品描述为 AGPL 与商业双许可，并对其所述服务及集成场景提出源码披露条件；[AGPL 原文](https://artifex.com/licensing/gnu-agpl-v3)列出具体条款。本草案不推断公开 GitHub 源码本身足以满足这些条款，也不替用户购买或签署商业授权。

在确认上述边界后，需要形成经逐组件核对的版权/归属与许可证文本清单，明确离线包内对应源码及用户获取方式，补齐产品级 `LICENSE` 和最终 `NOTICE`，并留下复核人、版本、日期、结论与差异处理记录。最终材料应与同一固定发行包的字节一致，再进行安装、升级和 Release Gate 验收；任一项缺失时继续保持 `release_eligible=false`。

本草案的事实来源还包括[CR-PKG-006](../changes/CR-PKG-006-ghostscript-source-candidate.md)。它不改变业务代码、数据库、API、安装服务或现有候选文件。
