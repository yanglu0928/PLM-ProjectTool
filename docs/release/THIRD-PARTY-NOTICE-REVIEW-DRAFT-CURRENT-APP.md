# 当前应用候选第三方通知审阅差异稿（非正式 NOTICE）

日期：2026-10-02；对象：Windows 11 当前应用**非发行**候选 SHA-256 `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`，来源提交 `6d731177aacb1cfd1ae57fa01ce99275fea49e24`。父包是[P45 固定非发行候选](THIRD-PARTY-NOTICE-REVIEW-DRAFT-P45.md)，SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`。本稿是逐字节继承核查后的**审阅差异**，不是产品级 `LICENSE`/`NOTICE`、法律意见、发行许可或 Gate 通过证明。

只读[核对工具](../../tools/audit_current_app_license_inheritance.py)固定两个 ZIP 的完整 SHA-256，再核对安全路径、清单全集、manifest、第三方库存原字节及保留文件的 SHA-256。父包中除自有后端包/其 dist-info 和前端 dist 之外的 20,573 项，在当前包中名称与清单哈希均相同；后端自有分发包的 `METADATA` 版本及 18 条 `Requires-Dist` 声明也相同。因此 P45 的**第三方材料字节与声明审阅输入**可继续用于当前候选，但这不证明源码、通知和法律义务已审结。该工具在固定 ZIP 上退出0，合成正常/篡改及错误哈希测试2/2通过。

|范围|可复用的精确输入|仍需形成的发行结论|
|---|---|---|
|原生 OCR|[34 PE、61 来源记录、42 原文](native-ocr-p45-review-inputs/REVIEW.md)及包内 `review-map.json`/文本哈希不变。|逐二进制确认适用许可证、版权归属、对应源码、修改及最终产品通知；原 `release_obligations_reviewed=NO` 不变。|
|Python 第三方|[105 项完整审阅清单](../progress/plt-pkg-01-a09-p43-a10-python-105-review-inputs.md)对应载荷不变；自有后端仍单列，不算第三方。|全部 `REVIEW_REQUIRED`；`bce-python-sdk` 尚无专属归属/通知映射，[共用 Apache 正文](../progress/plt-pkg-01-a09-p43-a08-bce-license-text-reuse.md)仅是技术复用候选。|
|Ghostscript、Caddy/Go、PostgreSQL/pgvector|P45 包内原二进制、源码和许可/库存文件均为继承载荷；[原差异分类](../progress/plt-pkg-01-a09-p43-a06-release-obligation-delta.md)可作为审阅输入。|各自的组合分发、下游模块、源码提供和通知条件仍须合格审阅；源码存在不等于履行义务。|
|前端与模型|前端第三方许可证据侧载和 OCR 模型原载荷不变；当前应用的前端 `dist` 为重新构建字节。|应核对重新构建前端所含第三方版本与侧载映射，不能仅用父包库存推定最终 NOTICE 完整。|
|本产品|当前包自有后端/前端已替换，原正式业务基线和候选身份可追溯。|产品许可选择、版权归属、产品级 `LICENSE` 与 `NOTICE` 尚缺，须与最终发行物字节绑定并有审阅人、日期、版本及批准记录。|

审阅结论栏保持空白，由有权发行负责人及合格人员填写：适用发行方式、逐组件义务/依据、对应源码提供方式、最终声明文本与签核记录。不得以用户计划公开源码或本差异稿推定 Ghostscript/整包许可已满足。当前 ZIP 明确 `legal_clearance=false`、`release_eligible=false`、`formal_tls_material_included=false`；正式信任、目标平台安装升级、AI 质量、UAT和 Gate 仍由[发行阻断复核](../progress/plt-pkg-01-a09-p48-a01-current-candidate-release-reconciliation.md)独立跟踪。
