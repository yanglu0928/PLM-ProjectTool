# Evidence 精确来源定位重新进入检查

日期：2026-10-01。结论：`PARTIAL_PRECONDITION_READY`。此项是对 2026-09-26 [旧前置核查](evd-01-a03-p02-a02-precision-precheck.md)的增量复查，不修改旧结论当时的证据，也不把精确定位改记为 PASS。

旧核查所指“尚无正式 Parser 结果”现在已不再成立：Parser 的 `structured_result.py` 已定义带版本、源文件 SHA、节点 ID 与来源位置的规范结果；Document 的 `LocalParseResultStorage.read_verified` 能在持有可信固定元数据时校验私有结果字节。Document 也已有 ParseResultRef 与成功 ParseRecord 持久化。它们为精确位置证明提供了必要材料，但不是 Evidence 已获授权读取的充分条件。

现有 `DocumentEvidenceProofService` 只接受 `DOCUMENT`，通过受权 Document 下载快照证明整个固定版本。它没有使用 ParseRecord/ResultRef 元数据，也没有跨 Document 边界的“现时授权＋固定版本绑定＋私有结果 Hash/大小回读＋节点定位”受控 Port。不能让 Evidence 直接读取 Document 私有表或物理路径。Parser 已发出 TEXT_RANGE、PAGE、PARAGRAPH、TABLE_CELL、SHEET_RANGE、SLIDE_SHAPE 等节点位置，但 SECTION 没有独立发出；STRUCTURED_NODE 还需绑定成功 ParseRecord 和真实节点。九种冻结 Locator 不得以一个通用全文 Hash 假装全部支持。

下一项限定为 `EVD-01-A03-P02-A02-P01`：先设计并验证 Document 所有的受权固定版本 ParseResult 读取 Port，然后只针对实际 Parser 已发出的定位类型逐项证明；SECTION/STRUCTURED_NODE 与各格式真实位置另列测试和关闭条件。输入必须是固定 DocumentVersion、当前有权用户、成功 ParseRecord、精确 ResultRef 与经 Hash 回读的不可变字节；篡改、旧版本、跨项目、无权限、空/失败解析及来源漂移全部失败关闭。不得调用外部 AI、修改已冻结 API，或把旧 PoC 解析器当作生产来源。

此检查仅只读代码和既有进度证据；未运行新测试、未改生产 API/Schema/Migration，Gate 3 仍 OPEN。Windows Server 2025 与 Debian 13 的正式验证状态不变。
