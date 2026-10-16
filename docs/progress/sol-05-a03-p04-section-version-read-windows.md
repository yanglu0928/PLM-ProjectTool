# SOL-05-A03-P04：SectionVersion 历史读取 Windows 组合与真实 ASGI/PG

日期：2026-10-12。结果：`SECTION_VERSION_READ_WINDOWS_PG_PASS`，仅 Windows 11 当前账户/一次性 PG18.6 的合成信任环境；正式服务账户、HTTPS、公钥与发行环境未验。

编码前检查：Phase 2 / 本 WBS；Gate2 API-04、CR-SOL-003、A03-P01 项目成员授权、A03-P02 内部 Owner、A03-P03 HTTP 合同均已验，前置满足。仅涉及 Solution Windows 组合、独立游标密钥、生产入口与验证；无 Schema/Migration、冻结路径/角色或历史数据变化。验收为显式平台读/写装配、缺密钥失败关闭/资源释放、五版本真实 PG HTTP 分页/详情与隔离/许可拒绝、不增加版本/Audit。风险是新增密钥导致旧部署无法直接启动、缺钥软降级和合成信任被误称正式信任。先登记 DEC-1184；装配中识别升级前置并补记 CR-SOL-020，不伪称该 CR 先于代码。

新增 `project-section-version-list-cursor-v1` 独立 32 字节 Windows 当前账户 Vault 引用，生产只读、缺失/错误长度统一拒启动且释放 Runtime，不自动创建或打印。`--platform` 与 `--platform-write` 组装真实 Session/License/Project 当前授权、Section 与 SectionVersion SQL Repository 和可选 GET/LIST Router；默认/登录专用模式不挂载，CREATE 优先装配不被只读 POST 关闭路由遮蔽。临时随机 Vault 引用验证丢失及加密备份恢复后旧游标可解，最终清理；正式目标引用未创建。

Windows 11 家庭版中文版实际运行：一次性 PG18.6 五个真实提交版本，经 Windows 工厂和 ASGI TestClient 验证三页倒序、详情固定 Document/Requirement/Evidence 引用、项目成员、匿名/错误会话/跨项目/不存在版本/License/篡改及跨会话游标拒绝、默认路由和只读 POST 关闭、数据库版本/Audit 数保持5，脚本退出0。生产组合合同在读/写两模式验证路由挂载及缺独立 key 拒启动/资源释放。定向 50 通过、63 子测试；补充 Vault 恢复 2 通过/3 子测试，生产组合两模式路由断言 2 通过。最终后端全量 3547 通过、3 跳过、5583 子测试，退出0。Alembic 自检有现存 operator/computed-default 比对 warning，但显示 `No new upgrade operations detected`；本项无迁移。

兼容/升级/回滚见 CR-SOL-020：先供给目标账户独立密钥及加密备份/恢复验证，再启用新版；可撤可选装配并恢复旧程序，历史不删。未验真实浏览器 UI、正式服务账户 Vault/ACL、HTTPS/发行公钥、Windows Server 2025、20 并发、Gate3/Pilot/Release；Debian13 实机按用户指令跳过。下一项 `SOL-05-A03-P05` 补 SectionVersion 列表/详情前端与 Windows 11 浏览器验收。TraceLink：Gate2 API-04 → CR-SOL-003 → A03-P02/P03 → DEC-1184/CR-SOL-020 → 本 P04 → P05 → Gate3/Pilot。
