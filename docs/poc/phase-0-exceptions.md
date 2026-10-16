# Phase 0 验证例外

## EXC-P0-001：暂缓 POC-01 Debian 13 验证

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-17|
|批准人|用户/项目负责人|
|关联 PoC|POC-01|
|例外内容|Debian 13 本轮暂不验证，跳过执行|
|已完成范围|Windows 11、Windows Server 2025|
|未验证范围|Debian 13 Python 3.13 依赖、离线安装及 OCR/PDF-A/deskew 链路|
|处理结果|POC-01 以 `PASS_WITH_EXCEPTION` 收口，可进入下一项 Phase 0 PoC|

## EXC-P0-001 边界

1. 本例外只调整当前 POC-01 的执行范围和顺序，不删除 Debian 13 正式兼容目标。
2. Windows 结果不得外推为 Debian 兼容性证据；Debian 13 状态保持 `DEFERRED_BY_USER / 未验证`。
3. 在声称 Debian 13 兼容、制作 Debian 发行包或通过 Debian Release Gate 前，必须恢复并完成对应验证。
4. 本例外不代表 Phase 0 整体完成；其他阻塞 PoC 仍须依次执行并通过或取得独立例外。

## EXC-P0-002：暂缓 POC-02 Windows 11 断网重放与 Debian 13 验证

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-17|
|批准人|用户/项目负责人|
|关联 PoC|POC-02|
|例外内容|暂缓 Windows 11 完全断网重放；暂缓 Debian 13 全套 POC-02 验证|
|已完成范围|Windows 11 功能链；Windows Server 2025 完全断网功能链|
|未验证范围|Windows 11 物理断网重放；Debian 13 PostgreSQL 18、pgvector、Alembic、HNSW、10 万向量、备份恢复与重启|
|处理结果|POC-02 以 `PASS_WITH_EXCEPTION` 收口，可进入下一项 Phase 0 PoC|

## EXC-P0-002 边界

1. Windows 11 已通过功能验证，但不得描述为已完成完全断网安装验证。
2. Windows Server 2025 的完全断网结果不得替代 Windows 11 或 Debian 13 的平台证据。
3. Debian 13 保持 `DEFERRED_BY_USER / 未验证`，不得据此声明 PostgreSQL 18 + pgvector 已兼容 Debian 13。
4. 在声称 Windows 11 完全离线兼容、制作 Debian 发行包或通过相应 Release Gate 前，必须恢复并完成对应验证。
5. 本例外仅允许 POC-02 阶段性收口，不改变三个正式目标环境，也不代表 Phase 0 整体完成。

## EXC-P0-003：暂缓 POC-04 Debian 13 验证

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-17|
|批准人|用户/项目负责人|
|关联 PoC|POC-04|
|例外内容|Debian 13 本轮暂不验证，跳过 POC-04 执行|
|已完成范围|Windows 11、Windows Server 2025 的统一 AI Gateway、确定性协议场景及真实 DeepSeek 调用|
|未验证范围|Debian 13 上的 Python 依赖、AI Gateway 协议行为及 DeepSeek 网络调用|
|处理结果|POC-04 以 `PASS_WITH_EXCEPTION` 收口，可进入下一项 Phase 0 PoC|

## EXC-P0-003 边界

1. 本例外只调整当前 POC-04 的执行范围和顺序，不删除 Debian 13 正式兼容目标。
2. Windows 11、Windows Server 2025 的结果不得外推为 Debian 13 兼容性证据；Debian 13 保持 `DEFERRED_BY_USER / 未验证`。
3. 在声称 Debian 13 AI Gateway 兼容、制作 Debian 发行包或通过 Debian Release Gate 前，必须恢复并完成对应验证。
4. 本例外不改变统一 `AIService → ModelRouter → ProviderAdapter` 基线，不允许业务模块直接调用厂商 SDK。
5. 本例外不代表 Phase 0 整体完成；其他阻塞 PoC 仍须通过或取得独立例外。

## EXC-P0-004：暂缓 POC-05 Windows 11 物理断网复跑与 Debian 13 验证

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-21|
|批准人|用户/项目负责人|
|关联 PoC|POC-05|
|例外内容|Windows 11 保留 `PASS_LOCAL_ASSETS`，不主动断开当前主机网络；Debian 13 本轮暂不验证|
|已完成范围|Windows 11 六类输入、主辅 OCR 功能链、26 个受支持真实文件、5 个真实扫描 PDF 的分层语义审计；Windows Server 2025 完全断网 8/8 功能链|
|未验证范围|Windows 11 物理断网复跑；Debian 13 六类格式、OCR、模型与运行制品验证|
|处理结果|POC-05 以 `PASS_WITH_EXCEPTION` 收口，可进入下一项 Phase 0 PoC|

## EXC-P0-004 边界

1. Windows 11 已使用显式本地模型和运行制品完成重放，但不得描述为已完成物理断网验证。
2. Windows Server 2025 的完全断网结果不得替代 Windows 11 或 Debian 13 平台证据。
3. Debian 13 保持 `DEFERRED_BY_USER / 未验证`；在制作 Debian 发行包或通过 Debian Release Gate 前必须恢复验证。
4. 真实扫描语义结论只覆盖 5 份文档中的 15 个分层抽样页和 75 个视觉检查点，不等同于 105 页逐字符全量标注。
5. PaddleOCR 为主链；未达门槛的 Tesseract 只能作为辅助回退，关键字段必须由主链或人工确认。
6. 本例外不改变三个正式目标环境，也不代表 Phase 0 整体完成；POC-03 质量 Gate 仍为 FAIL。

## EXC-P0-005：暂缓剩余 POC-06 / POC-08 / POC-09 Debian 13 验证

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-21|
|批准人|用户/项目负责人|
|关联 PoC|POC-06、POC-08、POC-09|
|例外内容|Debian 13 本轮不再验证，跳过 Word/PPT、Plugin Host 与 License 的 Debian 执行|
|已完成范围|POC-06 Windows 11 全链及 Windows Server 2025 包结构/Hash；POC-08、POC-09 的 Windows 11 与 Windows Server 2025 全链|
|未验证范围|Debian 13 的 Word/PPT 生成与打开、Plugin Host 进程/stdio 行为、MAC 枚举及 Ed25519 离线链|
|处理结果|POC-08、POC-09 以 `PASS_WITH_EXCEPTION` 收口；POC-06 解除 Debian 缺口，但仍因 Windows Server 2025 未安装 Microsoft Office 保持 `IN_PROGRESS`|

## EXC-P0-005 边界

1. 本例外只调整 Phase 0 当前验证范围，不删除 Debian 13 正式兼容目标。
2. Windows 11、Windows Server 2025 的结果不得外推为 Debian 13 兼容性证据；Debian 13 保持 `DEFERRED_BY_USER / 未验证`。
3. 在声称 Debian 13 兼容、制作 Debian 发行包或通过 Debian Release Gate 前，必须恢复并完成对应安装、License、Plugin 与输出验证。
4. POC-06 的 Windows Server 2025 Office 实开仍为独立阻塞，本例外不允许将包结构/Hash 结果描述为 Office 兼容通过。
5. 本例外不改变 Plugin 子进程、License Ed25519、Word/PPT 技术基线，也不代表 Phase 0 整体完成；POC-03 质量 Gate 仍为 FAIL。

## EXC-P0-006：POC-03 质量 Gate 批准替代方案

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-22|
|批准人|用户/项目负责人|
|关联 PoC|POC-03|
|原失败|50 条独立留出集 Top-5 49/50（98.00%）PASS；分类 24/50（48.00%）与精确引用 37/50（74.00%）低于 90%/98% 门槛|
|批准替代方案|保留历史 FAIL，不重写指标；采用 R11 双来源证据、Prompt v3、Evidence Selector 与所有 AI 建议强制人工确认；质量指标转为 Platform Core/UAT 阻塞项|
|平台边界|完整端到端质量复验仅在 Windows 11 执行；Windows Server 2025 的底层 Python、PostgreSQL/pgvector、文档与 AI Gateway 已由独立 PoC 验证；Debian 13 依据用户总体暂缓决定保持未验证|
|处理结果|POC-03 状态改为 `CLOSED_WITH_APPROVED_ALTERNATIVE`，允许 Phase 0 Gate 1 收口|

## EXC-P0-006 边界

1. 分类 48.00%、精确引用 74.00% 继续是正式失败证据，不得描述为达到质量门槛。
2. R11 仅完成离线合同和合成测试，不等同于真实模型质量 PASS。
3. AI 分类、引用和方案建议必须保持建议态，经人工确认后才能成为正式业务事实。
4. Gate 3/UAT 前必须以未用于调优的新独立留出集重新验证；任何客户数据外发仍需当轮明确授权。
5. 本例外不降低 90%/98% 目标，不允许事后改标签、泄露 Golden 字段或以格式正确替代内容质量。
6. 不得声称 Windows Server 2025 或 Debian 13 已完成 POC-03 端到端质量验证。

## EXC-P0-007：POC-06 Windows Server 2025 Office 实开例外

|字段|内容|
|---|---|
|状态|APPROVED|
|批准日期|2026-09-22|
|批准人|用户/项目负责人|
|关联 PoC|POC-06|
|例外内容|Windows Server 2025 未安装 Microsoft Office，不再要求本轮在 Server 实开 Word/PowerPoint|
|已完成范围|Windows 11 Office 实开、PDF 导出、100/50 页全量视觉检查；Windows Server 2025 OOXML 包结构与文件 Hash 复验|
|未验证范围|Windows Server 2025 本机 Microsoft Word/PowerPoint 实开与 PDF 导出；Debian 13 依据 `EXC-P0-005` 暂缓|
|处理结果|POC-06 以 `PASS_WITH_EXCEPTION` 收口，允许 Phase 0 Gate 1 收口|

## EXC-P0-007 边界

1. Microsoft Office 不是服务器运行依赖；本例外只豁免 Server 本机 Office 实开，不改变生成文件必须能由 Office 正常打开的产品要求。
2. Windows 11 的 Office 结果和 Server 的包结构/Hash 结果不得改写为“Windows Server 2025 Office 实开 PASS”。
3. 若未来 Server 发行方案要求在服务器安装或自动化 Microsoft Office，必须重新执行兼容性与商业许可审查。
4. DOCX/PPTX 的正式生成实现仍须遵守 `python-docx` / `python-pptx` 基线和 Release Regression。
