# 原生 OCR 许可文本审阅输入

此目录保存固定 Windows 11 非发行候选中的原生 OCR 许可材料原字节，供产品负责人和合格审阅人员核对组件归属。来源候选 SHA-256 为 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；[导出记录](../../progress/plt-pkg-01-a09-p46-a02-notice-review-inputs.md)说明核验方法。本目录不是最终产品 NOTICE、法律批准或发行包。

`review-map.json` 含 34 个原生 PE、61 条来源记录和 42 个不同正文哈希。按每条记录的 `text_sha256` 打开 `texts/{sha256}.txt`，即可查看对应原始文本。`README.txt` 与这 42 个文本及映射均与固定候选内的侧载同字节；本 `REVIEW.md` 是仓库另加的审阅说明，不在候选 ZIP 内。导出源文件共 44 项、354,131 字节，映射 SHA-256 为 `b60406e8d462cde5a79eaed362df68c465b1a96db346cff90bc9e9e41c09e1fb`。仓库为这 44 项关闭 Git 文本换行规范化，以保留上游原有行尾空格与字节哈希。

审阅时应逐组件确认发行物的准确名称/版本、该文本是否适用于相应二进制、归属与版权文字、对应源码及修改材料是否充分、产品级通知的表达与提供方式。共享正文只表示哈希相同，不表示 61 条义务都已满足。映射中的 `release_obligations_reviewed` 均保持 `NO`，`legal_clearance=false`、`release_eligible=false`；任何结论须另留审阅人、日期、版本、依据和差异处理记录，不要直接修改原始映射以伪装已审结。

完整产品级第三方缺口及其他组件见[当前候选 NOTICE 审阅草案](../THIRD-PARTY-NOTICE-REVIEW-DRAFT-P45.md)。
