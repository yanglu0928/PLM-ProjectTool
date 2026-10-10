# 当前候选第三方通知审阅草案

此草案面向产品负责人及合格法律审阅人员，汇总 Windows 11 原生 OCR 通知非发行候选的材料和待审决定。固定候选 SHA-256 为 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，不是此前[P43 草案](THIRD-PARTY-NOTICE-REVIEW-DRAFT.md)的 SHA；P43 的 21,114 项原载荷在新候选中逐项保持不变，新增 42 份原文、映射和 README 共 44 项。此文不是最终 LICENSE/NOTICE 或发行批准，候选继续 `release_eligible=false`。

## 已定位的材料

|组件范围|当前候选材料|未完成的审阅|
|---|---|---|
|原生 OCR 依赖|[可由 GitHub 直接读取的审阅输入](native-ocr-p45-review-inputs/REVIEW.md)：34 个 PE、61 条来源记录、42 份去重原文；[字节来源审计](../progress/plt-pkg-01-a09-p45-a02-native-license-source-bytes.md)已从精确原始归档回读。|逐 PE 确认文本适用性、归属、对应源码/修改与产品通知；全部 `release_obligations_reviewed=NO`，不得据材料存在认定合规。|
|Ghostscript 10.08.0|随包可执行文件、`doc/COPYING`、同版官方源码及 LICENSE。|合格人员确认本产品发行方式、源码提供和组合义务；源码在包内不自动意味着法律放行。|
|Caddy 2.11.4、Go 1.26.3|根 LICENSE、149 项 SBOM、Caddy 可构建源码、Go 标准库源码及 LICENSE。|逐项核对下游模块、归属、通知和源代码材料；149 项清单不是 149 项已审结。|
|PostgreSQL 18.6、pgvector 0.8.6|服务器/工具许可文本、pgvector LICENSE 与运行文件。|核对发行物及传递原生依赖的归属与许可证据。|
|Python 第三方包|[105 项完整输入](../progress/plt-pkg-01-a09-p43-a10-python-105-review-inputs.md)适用于 P43 原载荷，P45 未改变这些字节；102 项有内嵌材料、2 项仅侧载、1 项缺专属通知。|全部仍为 `REVIEW_REQUIRED`；`bce-python-sdk` 专属归属/通知待补，许可证表达式空值的 60 项须逐件判断。|
|前端与 OCR 模型|6 份前端独立许可侧载与模型说明文件。|逐项核对生产依赖、模型来源、归属和通知条件。|

上述数量来自[P43 发行证据分类](../progress/plt-pkg-01-a09-p43-a06-release-obligation-delta.md)、[Python 材料审计](../progress/plt-pkg-01-a09-p43-a10-python-105-review-inputs.md)和[P45 新侧载](../progress/plt-pkg-01-a09-p45-a03-native-ocr-notice-candidate.md)，并非法律审核完成数。当前 ZIP 根目录没有产品级 `LICENSE` 或 `NOTICE`；包内 `payload/runtime/LICENSE.txt` 属运行时，不是本产品许可声明。

## 审阅人需要形成的结果

产品许可与分发方式须先由有权人员确定；各组件须分别留下适用许可、版权归属、对应源码/修改、通知内容与提供方式的结论。最终产品级 LICENSE/NOTICE 应与一个后续固定发行候选的实际字节对应，并记录审阅人、日期、版本、差异和批准结论。AI 不代替该判断，也不将“计划公开源代码”直接认定为满足所有第三方义务。法律材料审结后，仍需正式信任源、目标平台安装/升级、AI 质量及 Release Gate 证据；[发行阻断清单](../progress/plt-pkg-01-a09-p46-a01-release-blocker-register.md)分别追踪这些独立条件。
