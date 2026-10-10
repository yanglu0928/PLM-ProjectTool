# Phase 0 技术验证总结

## Gate 结果

|字段|结果|
|---|---|
|阶段|Phase 0 技术验证|
|执行期间|2026-09-17 ～ 2026-09-22|
|Gate 1|APPROVED（2026-09-22，用户/项目负责人）|
|阶段结论|`COMPLETE_WITH_APPROVED_ALTERNATIVES`|
|下一阶段|Architecture Freeze → Data Model Freeze → API Contract Freeze|

Gate 1 通过不等同于所有平台和质量指标均已验证。未验证范围、失败指标和批准替代方案继续构成后续 Gate、UAT 与 Release 的约束。

## PoC 汇总

|PoC|结论|关键证据|例外/遗留|
|---|---|---|---|
|POC-01 Python 3.13|PASS_WITH_EXCEPTION|Windows 11 / Server 2025 离线依赖与 OCR/PDF 链通过|Debian 13 暂缓，`EXC-P0-001`|
|POC-02 PostgreSQL 18 + pgvector|PASS_WITH_EXCEPTION|Windows 双平台功能链；Server 完全断网；10 万向量/HNSW/备份恢复通过|Windows 11 物理断网、Debian 暂缓，`EXC-P0-002`|
|POC-03 PLM RAG|CLOSED_WITH_APPROVED_ALTERNATIVE|Top-5 49/50（98.00%）PASS；分类 24/50（48.00%）、引用 37/50（74.00%）FAIL|保留失败，R11 + 强制人工确认；Gate 3/UAT 新留出集复验，`EXC-P0-006`|
|POC-04 AI Gateway|PASS_WITH_EXCEPTION|Windows 双平台真实文本、流式、结构化及错误场景通过|Debian 暂缓，`EXC-P0-003`|
|POC-05 Document + OCR|PASS_WITH_EXCEPTION|六类输入；Server 完全断网；PaddleOCR 75/75、关键错误 0|Windows 11 物理断网、Debian 暂缓，`EXC-P0-004`|
|POC-06 Word / PPT|PASS_WITH_EXCEPTION|Windows 11 Office 实开、100/50 页与 150 页视觉检查；Server 包结构/Hash 通过|Server Office 实开豁免、Debian 暂缓，`EXC-P0-005/007`|
|POC-07 VSDX|DEFERRED_P1|不属于 Phase 0 阻塞项|P1 执行|
|POC-08 Plugin Host|PASS_WITH_EXCEPTION|Windows 双平台 13/13 测试、10/10 场景、20 并发；宿主未崩溃|Debian 暂缓，`EXC-P0-005`|
|POC-09 License|PASS_WITH_EXCEPTION|Windows 双平台 26/26 测试、10/10 场景；8/8 非法授权拒绝|Debian 暂缓，`EXC-P0-005`|

## 冻结阶段输入

- 正式架构保持模块化单体，不拆微服务。
- 数据基线保持 PostgreSQL 18 + pgvector + 本地文件元数据化管理。
- AI 统一通过 `AIService`；RAG 统一平台并按 ProjectId 隔离。
- Plugin 保持 Python 独立子进程 + JSON-RPC over stdio。
- License 保持显式 MAC 选择、规范化、SHA-256 与 Ed25519；私钥只在开发者工作台。
- Windows 11、Windows Server 2025、Debian 13 仍是正式兼容目标；Debian 未验证范围不得宣称通过。

## 强制遗留约束

1. POC-03 的 48.00% 分类与 74.00% 引用继续是失败事实；任何 AI 产物保持建议态并强制人工确认。
2. Gate 3/UAT 前使用全新独立留出集验证分类 ≥90%、精确引用 ≥98%；新外发须重新授权。
3. Windows Server 2025 Office 实开没有执行；不得把相同 Hash/OOXML 描述为 Server Office PASS。
4. Debian 13 全部批准暂缓项不形成兼容性证据；Debian Release Gate 前必须恢复验证。
5. Architecture、Data Model、DB Schema V1、API Contract V1 未冻结前，不得开始正式业务编码。

## 下一步

执行 AF-01 Architecture Baseline Consolidation：收敛模块边界、依赖方向、统一服务接口、安全边界和 PoC 遗留约束；形成 Architecture Freeze 候选及 ADR 集。随后依次完成 Data Model Freeze 和 API Contract Freeze，并在 Gate 2 请求正式确认。
