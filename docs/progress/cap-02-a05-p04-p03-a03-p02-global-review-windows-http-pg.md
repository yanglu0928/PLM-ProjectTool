# CAP-02-A05-P04-P03-A03-P02：GLOBAL Capability Review Windows 装配与 HTTP/PG

日期：2026-10-24；结果：`WINDOWS_11_SYNTHETIC_HTTP_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A03-P02`，仅在 Windows Capability 显式写模式装配已通过合同的 GLOBAL Review GET/DECIDE。|
|输入基线/前置|Gate 2 原 PROJECT API 不改；`CR-CAP-005`、A02 内部服务/隔离 PG 和 A03-P01 HTTP 合同已通过。|
|模块/实体/API|Capability/Review 组合根、Review/Capability Version 既有实体；新增 GLOBAL 两条路由仅由 `--platform-write` 启用。无 ORM/Migration 变化。|
|权限/风险|当前 Session、License、可信 Origin/CSRF、受分配且启用的 Reviewer；来源撤销、未分配者或错误 Scope 必须失败关闭；合成信任不得当正式安装。|
|验收|组合单元/生产工厂合同、Windows 11 隔离 PostgreSQL 18 实际 HTTP 正负例、后端全量回归、临时库和服务复位。|

Windows 组合根复用同一 Review Repository、Subject Owner、Audit 和收据；GET 使用当前 Session/身份/License，POST 使用当前 Session/CSRF 和同事务决定服务。默认应用及只读模式不装配该 Router。合成 HTTP 夹具从 GLOBAL 文档/Evidence 生成 Capability 版本并送审，核对管理员和普通受分配者读取、未分配者 404、许可 403、错误 CSRF 401、两位受分配者依次批准、同 Key 相同结果及批准后 Version 状态；夹具数据库已删除。

测试：组合与生产合同定向 51 通过/31 子例；Windows 11/PG18.6 合成 HTTP 夹具退出 0，Alembic 无新增升级操作；后端全量 4087 通过/3 跳过/6129 子例、2 个既有警告。首轮全量因生产合同测试替身仍为旧三字段而失败 20 项，已更新替身并重跑全绿；失败未隐瞒。PoC PG 服务起初停止、测试期间临时启动、结束后恢复停止；`cap01a05a07_%` 临时库 0。

限制：仅 Windows 11 合成 Session/License/密钥，不是正式生产组合启动、真实人工评审或客户确认；Edge 页面、固定非发行包、正式发行公钥/目标账户、离线安装升级、Gate/Pilot/Release 仍未通过。Windows Server 2025、Debian 13 未实测。
