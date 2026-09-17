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
