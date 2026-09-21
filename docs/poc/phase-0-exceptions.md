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
