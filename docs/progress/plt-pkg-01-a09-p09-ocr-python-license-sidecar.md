# PLT-PKG-01-A09-P09：新增13项OCR Python许可文本独立侧载

日期：2026-10-01；状态：`NON_RELEASE_NOTICE_SIDECAR_INTEGRITY_PASS / LEGAL_REVIEW_OPEN`。

编码前检查：Phase 2 / 本 WBS；输入为 A09-P02 固定候选（SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`）与 A09-P08 机读差异清单（SHA-256 `b0deecb9cd6c422ded0a5aa95cd08a93f488199a3025b2cb09f6ec08fd54f717`）。本项只复制新增13项运行时`.dist-info`中的25份原始文本到新的非发行旁包；不改旧/统一ZIP、产品许可证、业务实体、API、权限或Migration。验收为固定输入、路径安全、来源成员与Hash、输出逐件回读、拒绝重名/伪发行/覆盖。风险是文本不是源码/组合义务结论；丢弃新旁包和脚本即可回滚。

输出：`artifacts/package-prep/windows11/NOT-FOR-RELEASE-ocr-python-license-sidecar-20261001.zip`，77,854字节，SHA-256 `a9a2ef6f295ac01d14561a64f6b0b5fe3f83d1535dc899b2893576ca0282e71e`。ZIP内25份文本与1份manifest，25/25来源Hash和回读Hash一致；manifest固定13项、`corresponding_source_included=false`、`legal_clearance=false`、`release_eligible=false`。本地ZIP被Git忽略，不对客户发布；代码、测试和记录同步GitHub。

单元4/4通过：精确25项集合、路径越界、大小写折叠重名及伪发行声明拒绝。第一次单元测试因构造的“大写路径”先触发来源前缀拒绝，修正测试输入为同前缀文件名大小写重名后重跑4/4通过；未放松生产校验。当前统一候选**尚未并入该旁包**，不能说其独立许可侧载已完整；下一项需生成新非发行ZIP并再次逐件Hash/清洁解包。34项原生、Ghostscript/模型/前端、项目`LICENSE`/`NOTICE`、对应源码与有资质复核仍开放，`release_eligible=false`。
