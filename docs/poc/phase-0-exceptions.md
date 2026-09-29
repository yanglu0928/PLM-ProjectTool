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

## 边界

1. 本例外只调整当前 POC-01 的执行范围和顺序，不删除 Debian 13 正式兼容目标。
2. Windows 结果不得外推为 Debian 兼容性证据；Debian 13 状态保持 `DEFERRED_BY_USER / 未验证`。
3. 在声称 Debian 13 兼容、制作 Debian 发行包或通过 Debian Release Gate 前，必须恢复并完成对应验证。
4. 本例外不代表 Phase 0 整体完成；其他阻塞 PoC 仍须依次执行并通过或取得独立例外。
