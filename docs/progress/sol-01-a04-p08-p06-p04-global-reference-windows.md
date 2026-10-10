# SOL-01-A04-P08-P06-P04：GLOBAL Reference Windows 显式组合

日期：2026-10-09。结果：`GLOBAL_REFERENCE_WINDOWS_PASS`，限定 Windows 11 合成隔离验证；正式服务账户/License、真人业务确认和发行验收未通过。

编码前检查：依 P06-P01～P03、冻结 API-04 六字段和现有 Windows PROJECT Create/人工脱敏确认装配。只改 Solution Reference Windows 组合、生产写模式入口、对应测试与验收脚本；无 Schema、依赖、权限、冻结合同或数据迁移变化。写模式已有 Document/Evidence 当前固定证明、Session/Origin、License 和 Audit 端口；缺任何必要端口立即启动失败，不隐式降为宽松实现。

实现：新增 `create_windows_global_reference_create_router`，显式装配同一 `ReferenceCreateService`、当前 GLOBAL 管理员授权、物理文件/解析结果/Evidence 来源证明、确认账本、幂等和 Audit。仅 `create_production_platform_write_app` 挂入 GLOBAL POST；登录模式及只读平台模式仍 404，写模式无凭证请求 403。GLOBAL 创建仍不接收确认 ID、不从脚本自动承认业务脱敏、不提高历史重放的当前资格。

验证：Windows 组合单元和生产入口合同覆盖可用/缺依赖失败关闭、只读 404/写模式已挂载；隔离 PG18.6/真实 Session/私有文件运行 P06-P03 全部正负例并退出 0。后端全量结果见 STATUS/版本说明。本项合成确认仅证明技术链路；正式 License、公钥/目标账户信任、Server 2025、真人核查、20 并发、Gate 3/UAT/发行仍待，Debian 13 依指令跳过。

兼容/升级/回滚：写模式新增原冻结 API 的 GLOBAL POST，原 PROJECT 和只读入口不变；无数据库升级。回滚移除写模式路由挂载；已产生的 Reference/确认/审计/收据保留不可删除。

TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P01/P02/P03 → 本 P06-P04 → P06-P05 前端。
