# 当前候选第三方通知审阅输入

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P46-A02`；结果：`NON_RELEASE_NATIVE_OCR_REVIEW_PACKET_EXPORTED / LEGAL_REVIEW_OPEN`。此项使 P45 候选的原生 OCR 许可材料可从 GitHub 获取，同时保留 P43 历史草案；它没有生成最终产品 LICENSE/NOTICE。

导出器先独立核固定 P45 ZIP SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、P43/P33/P22 谱系及 34 项 PE 矩阵，然后仅提取 `payload/third-party-licenses/native-ocr/` 下的 42 份文本、61 条映射与 README。源字节共 44 项、354,131 字节，映射 SHA-256 `b60406e8d462cde5a79eaed362df68c465b1a96db346cff90bc9e9e41c09e1fb`；导出时逐件 Hash/读回，另用 PowerShell 根据 61 条映射重新计算目标文件 Hash，42 个唯一正文、0 个缺失/错误。定向单元 2/2，真实导出退出 0；映射未含本机绝对路径或已知 Secret 模式。部分上游文本自带行尾空格，已用精确路径的 `.gitattributes -text` 保留原字节，44 项 Git 索引对象与工作文件原始对象哈希全部一致，不对原文作格式清理。审阅字节位于[原生 OCR 输入目录](../release/native-ocr-p45-review-inputs/REVIEW.md)，仓库额外的 `REVIEW.md` 不属于原候选侧载。

[P45 审阅草案](../release/THIRD-PARTY-NOTICE-REVIEW-DRAFT-P45.md)以当前候选为基准，把新增原生 OCR 证据与未变的 Python、Caddy/Go、PostgreSQL/pgvector、Ghostscript、前端及模型审阅队列关联；[P43 历史草案](../release/THIRD-PARTY-NOTICE-REVIEW-DRAFT.md)不追写其固定 SHA。共享正文及声明字段不推定许可证适用、源码义务或发行许可结论；产品级 LICENSE/NOTICE 与合格法律签核仍缺，`release_eligible=false`、`legal_clearance=false`。

兼容性：只增审阅材料、导出器与文档，不改 ZIP、API、Schema、Migration、SCM、正式安装或客户资料。升级：无迁移。回滚：弃用审阅目录即可，固定候选及历史文档仍可读。下一项转向 Gate 3 的全新独立留出集本地准备；对外模型调用和客户正文外发仍需当轮明确授权。
