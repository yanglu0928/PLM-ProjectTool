# SOL-01-A04-P08-P03-P05：GLOBAL 人工脱敏确认 Windows 显式组合

日期：2026-10-09；结果：`GLOBAL_ATTESTATION_WINDOWS_PG_PASS`，Windows 11 隔离 PG18.6/合成管理员和来源的显式写模式组合通过；实际人类业务确认与正式运行账户未验。

编码前检查：Phase 2；WBS P08-P03-P05；输入 CR-SOL-009、P08-P02 增量合同和 P03-P03/P04 HTTP/PG 证据；前置 Session、License Guard、Document/Evidence 固定来源 Owner、确认/撤回服务已完成。涉及 Solution Windows 组合根、GLOBAL Confirmation/Audit/幂等收据及三项增量 POST；只允许 DeploymentAdmin、当前 Session/CSRF、有效 License 和可信 Origin。验收为缺依赖拒启动、默认/只读无路由、显式写模式真实端口接线与隔离 PG/HTTP 全链；风险为错误开放到只读/默认模式或把合成管理员请求当成真人确认。

在现有 PROJECT Reference 组合中抽出共用来源 Proof 构造，新增 GLOBAL Preview/Confirm/Revoke Windows 组合：当前 Document、私有文件下载、解析结果、Evidence 与管理员来源证明；确认/撤回使用持久 Repository、同事务幂等收据与 Audit。仅 `include_secret_write` 显式模式注入 Router；默认应用和只读模式不挂载，GLOBAL Reference Create 继续关闭。无新密钥或独立外发。

验证：Windows 组合单元缺失依赖/路由白名单、生产模式合同共 `41 passed, 40 subtests`，确认只读模式 Preview/Confirm 404、写模式先执行安全校验；独立 Win11 PG18.6/真实 Session/合成 GLOBAL Document/Evidence/私有文件/ASGI 使用该组合完成 Preview 200、指纹漂移 409、Confirm 201/重放/异载荷冲突、Revoke 200/重放、单次 Audit，并继续执行文件/解析节点篡改与 Evidence 撤回回归，脚本退出 0；后端全量 `3331 passed, 3 skipped, 4927 subtests passed`。隔离 PG 已停止并清理。

兼容/升级：既有冻结 API/Schema/依赖不变，仅显式写模式新增受控接口；无数据迁移。回滚为撤销该组合根注入，确认历史/Audit 不得删除，原冻结接口不受影响。未验：前端逐项文档查看与显式声明、实际人类核查、正式 License 公钥/服务账户、安全代理、Server 2025、20 并发/Gate 3/发行；Debian 13 依用户指令跳过。TraceLink：CR-SOL-009 → P08-P02 合同 → P03-P01～P04 → P03-P05 Windows 组合/PG/全量 → 后续 UI/Edge。
