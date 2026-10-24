# DOCX V2 标题来源节点

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P04-A03`。结论：`PARSER_V2_INTERNAL_PASS`，不代表 SECTION Evidence 已可创建。

按照 [CR-EVD-001](../changes/CR-EVD-001-docx-section-source.md)，新 DOCX 计划使用 Parser Version 2，其他格式仍为 1。V2 保留原段落节点，额外将正文非空且样式 ID 精确为内置 `Heading1`～`Heading9` 的段落输出为 `DOCX_SECTION`。`SECTION` 路径 `word/heading/<level>/<paragraph_index>` 同时给出级别与固定正文段落序号；重名标题仍有唯一锚点。普通、自定义样式和空标题不产生章节节点。旧 V1 DOCX 结果仍可构造，V1 结果携带 V2 节点会拒绝；不追写旧 ParseRecord。

落盘合成 DOCX 经 Parser 提取后，由独立重新打开的 `python-docx` 按章节锚点核对真实段落样式和文字，脚本退出 0。Office 提取定向 7/7、Profile 定向 3/3，后端全量 1,745 项 OK（3 项既有跳过）。开发 wheel SHA-256 `113035bc660c220084d168e188f037d2bb91111f824692cd3fb54db1988f0183`，已检查包含三个变更的 Parser 模块。

Changed：Parser profile 选择、规范节点/位置和 DOCX 提取器及回归测试。公开 API、ORM/Schema、权限和第三方依赖：无变化；Migration：无。升级须先使旧 Parser Worker 静止并排空或按已有恢复流程处理 RUNNING V1 尝试；不能在新代码下默默续跑。Evidence 当前仍拒绝 SECTION，隔离 PostgreSQL V1/V2 共存及实际部署排空尚未验证，CR 和 Gate 3 保持开放。下一项仅接入固定结果上的 SECTION 节点证明。
