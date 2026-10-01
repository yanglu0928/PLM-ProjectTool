# PLT-PKG-01-A09-P08：统一候选许可与对应源码证据差异

日期：2026-10-01；状态：`EVIDENCE_GAPS_IDENTIFIED / RELEASE_BLOCKED`。机读结果见 [统一候选差异清单](plt-pkg-01-a09-p08-unified-license-gaps.json)，SHA-256 `b0deecb9cd6c422ded0a5aa95cd08a93f488199a3025b2cb09f6ec08fd54f717`。

## 编码前检查

- 当前Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P08`。输入基线：Gate2、ADR-002、CR-PKG-004、A09-P02统一非发行候选；既有93项后端许可候选和34项无JBIG原生来源矩阵均已固定Hash。
- 涉及模块：离线审计脚本及证据JSON；实体/API/权限/Migration：无，不更改产品许可证、GitHub可见性或客户交付状态。
- 验收：精确核固定两个ZIP/CSV，93项原依赖身份与版本不变，新增13项逐件定位包内文本/Hash，34项PE逐字节对矩阵，识别Ghostscript文本/模型声明/产品LICENSE与NOTICE/对应源码交付缺口；坏差异失败关闭。不得把文件存在、元数据表达式或脚本输出当作法律批准。
- 风险/回滚：此清单只覆盖固定Windows候选而非全部依赖的最终法律分类；保留历史候选，撤审计脚本/新JSON即可回滚，发行门禁仍关闭。

## 本机结果

- 固定统一ZIP SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`。旧93项Python发行身份/版本93/93不变；新增13项（`defusedxml`、`fonttools`、`fpdf2`、`img2pdf`、`markdown-it-py`、`mdurl`、`ocrmypdf`、`pdfminer.six`、`pikepdf`、`pluggy`、`Pygments`、`rich`、`uharfbuzz`），运行时内25份文本逐件Hash可定位，但既有独立许可侧载目录对这13项覆盖0/13。部分METADATA的`License-Expression`为空，不能据此判断其条款不存在。旧侧载文件数保持152。
- 新34项Tesseract PE与来源矩阵34/34字节一致；矩阵中34/34项`release_obligations_reviewed=NO`。这只是来源定位，不代表对应源码、适用许可、版权和重链接义务已经履行。
- 统一包内有Ghostscript `doc/COPYING`（AGPLv3文本，SHA-256 `57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6`），但候选内`payload/third-party-sources/`为0件；这**不证明**其他渠道不存在源码，只证明本候选尚未建立可核的源码交付目录。两个Paddle模型README声明`apache-2.0`，没有为这两个模型单独包装许可原文。仓库根目录当前无产品`LICENSE`/`NOTICE`。
- 单元4/4通过，覆盖精确13项差异、旧版本变化、重复身份与计数错误拒绝；真实固定字节审计通过。未修改GitHub仓库可见性，未核其当前公开状态；未聘请或替代有资质法律复核。

## 发行门禁与下一步

ADR-002要求包含Ghostscript的对外发行前完成公开源码、兼容的产品许可证、对应源码及第三方声明。Ghostscript[官方下载页](https://ghostscript.com/releases/gsdnld.html)与[官方FAQ](https://ghostscript.com/faq/)区分AGPL和商业路径；[GNU AGPLv3正文](https://www.gnu.org/licenses/agpl-3.0.html)是条款来源。本项目按已选AGPL路径继续准备技术和证据材料，但本审计不解释最终组合许可效力，更不声称已获发行许可。

下一独立任务：从新增13项开始生成精确版本/Hash的独立许可侧载候选，并核对应源码可获得性；34项原生、Ghostscript、模型、前端及项目许可证仍须合并审查。正式可用包还缺PostgreSQL18/pgvector离线输入、签名/License、目标账户/Server2025、真实质量和完整Gate。`release_eligible=false`。
