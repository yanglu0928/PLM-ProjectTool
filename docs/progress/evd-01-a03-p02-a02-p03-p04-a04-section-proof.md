# DOCX 标题的 SECTION 证明

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P04-A04`。结论：`SECTION_INTERNAL_SYNTHETIC_PASS`，仅覆盖 DOCX V2 内置标题与合成固定结果。

Evidence 继续只经 Document 所有的受权固定 ParseResult Port 取结果。只有 Profile 为 DOCX、Parser Version 为 2、节点类型为 `DOCX_SECTION`，且节点 ID 与规范 `word/heading/<level>/<paragraph_index>` 位置相符时，才可证明 SECTION。直接 Locator 和绑定 ParseRecordId/NodeId 的 STRUCTURED_NODE 均要求唯一真实节点；V1、普通段落、错误页序/路径和其他格式不因此获得 SECTION 权限。DOCUMENT 全文证明保持原路径。

临时落盘 DOCX 有两个内置标题及一个同名普通段落。正式 Parser 生成 V2 结果后，独立重开 DOCX 核对标题样式与位置，Evidence 对两个标题出具指纹一致的证明，对普通段落伪造的 SECTION 拒绝；脚本退出 0。Evidence 定向 9/9、后端全量 1,746 项 OK（3 项既有跳过）。开发 wheel SHA-256 `e139da178c72f0ed5c66d4941dce748dd2732a74be7d9986f1cf86f4584fe5ae`，包含变更模块。

Changed：Evidence 内部节点证明、单元测试、合成落盘验证。公开 API、ORM/Schema、权限和依赖：无变化；Migration：无。兼容性：旧 DOCX V1 结果仍可证明原段落，但不得证明 SECTION；升级遵守 [CR-EVD-001](../changes/CR-EVD-001-docx-section-source.md) 的旧作业静止/排空要求。

已知边界：本项 Document Port 为合成固定结果，不是隔离 PostgreSQL 的 V1/V2 共存端到端；正式用户 Session、跨项目撤权、旧作业升级排空、其他格式章节、客户文档质量、目标环境与 Gate 3 仍未完成。下一项用隔离 PostgreSQL 复核真实固定结果与跨版本共存。
